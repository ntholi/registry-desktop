from __future__ import annotations

import argparse
import json
import logging
import math
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Sequence

from bs4 import BeautifulSoup
from sqlalchemy import create_engine, func, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.orm import Session

from base.browser import BASE_URL, Browser
from base.runtime_config import (
    get_current_cms_base_url,
    get_current_country_code,
    get_current_country_label,
    has_complete_runtime_configuration,
)
from database import (
    Module,
    NextOfKin,
    Program,
    School,
    SemesterModule,
    Sponsor,
    Structure,
    StructureSemester,
    Student,
    StudentEducation,
    StudentModule,
    StudentProgram,
    StudentSemester,
)
from database.connection import configure_database_urls_for_country, get_database_url
from features.sync.modules.repository import ModuleRepository
from features.sync.modules.service import ModuleSyncService
from features.sync.structures.repository import StructureRepository
from features.sync.structures.service import SchoolSyncService
from features.sync.students.repository import StudentRepository
from features.sync.students.scraper import (
    _extract_student_id_from_row,
    extract_student_education_ids,
    extract_student_module_ids,
    extract_student_program_ids,
    extract_student_semester_ids,
    get_table_value,
    parse_semester_number,
    scrape_student_addresses,
    scrape_student_education_data,
    scrape_student_module_data,
    scrape_student_personal_view,
    scrape_student_program_data,
    scrape_student_view,
)
from features.sync.students.service import StudentSyncService
from tools.catalog_audit import (
    create_audit_database,
    drop_audit_database,
    patch_database_url,
)
from utils.normalizers import (
    normalize_date,
    normalize_next_of_kin_relationship,
    normalize_phone,
    normalize_program_status,
    normalize_semester_status,
    normalize_text,
)

STUDENT_FIELD_NAMES = (
    "name",
    "national_id",
    "date_of_birth",
    "phone1",
    "phone2",
    "gender",
    "marital_status",
    "country",
    "race",
    "nationality",
    "birth_place",
    "religion",
)

IMPORT_OPTIONS = {
    "student_info": True,
    "personal_info": True,
    "education_history": True,
    "enrollment_data": True,
    "addresses": True,
    "skip_active_term": False,
    "delete_programs_before_import": False,
}


@dataclass(frozen=True)
class CandidateProfile:
    student_number: str
    programs: int
    educations: int
    addresses: int
    semesters: int
    modules: int

    @property
    def score(self) -> tuple[int, int, int, int, int, str]:
        return (
            self.modules,
            self.semesters,
            self.educations,
            self.addresses,
            self.programs,
            self.student_number,
        )


@dataclass(frozen=True)
class AuditStudentResult:
    student_number: str
    import_succeeded: bool
    mismatch_sections: tuple[str, ...]
    duration_seconds: float
    live_counts: dict[str, int]
    mismatch_details: dict[str, Any]
    error: str | None = None


def normalize_float(value: Any) -> float:
    return round(float(value or 0.0), 4)


def normalize_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def sample_rows(rows: set[tuple[Any, ...]], limit: int = 5) -> list[list[Any]]:
    return [list(row) for row in sorted(rows)[:limit]]


def diff_summary(
    expected: set[tuple[Any, ...]], actual: set[tuple[Any, ...]]
) -> dict[str, Any]:
    missing = expected - actual
    extra = actual - expected
    return {
        "expected_count": len(expected),
        "actual_count": len(actual),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "missing_samples": sample_rows(missing),
        "extra_samples": sample_rows(extra),
    }


def build_page_starts(
    total_records: int, page_size: int, sample_pages: int
) -> list[int]:
    if total_records <= 0 or page_size <= 0 or sample_pages <= 0:
        return []

    page_count = max(1, math.ceil(total_records / page_size))
    requested = min(sample_pages, page_count)
    starts: list[int] = []
    seen: set[int] = set()

    for index in range(requested):
        target_page = round(index * (page_count - 1) / max(requested - 1, 1))
        start = (target_page * page_size) + 1
        if start in seen:
            continue
        seen.add(start)
        starts.append(start)

    return starts


def select_audit_students(
    candidates: Sequence[CandidateProfile], limit: int
) -> list[CandidateProfile]:
    if limit <= 0:
        return []

    rich_candidates = sorted(candidates, key=lambda item: item.score, reverse=True)
    ordered_candidates = sorted(candidates, key=lambda item: int(item.student_number))

    selected: list[CandidateProfile] = []
    selected_numbers: set[str] = set()

    rich_quota = min(len(rich_candidates), max(1, round(limit * 0.7)))
    for candidate in rich_candidates[:rich_quota]:
        if candidate.student_number in selected_numbers:
            continue
        selected.append(candidate)
        selected_numbers.add(candidate.student_number)

    remaining = max(0, limit - len(selected))
    if remaining:
        positions = build_page_starts(len(ordered_candidates), 1, remaining)
        for position in positions:
            candidate = ordered_candidates[position - 1]
            if candidate.student_number in selected_numbers:
                continue
            selected.append(candidate)
            selected_numbers.add(candidate.student_number)

    if len(selected) < limit:
        for candidate in rich_candidates:
            if candidate.student_number in selected_numbers:
                continue
            selected.append(candidate)
            selected_numbers.add(candidate.student_number)
            if len(selected) >= limit:
                break

    return selected[:limit]


def require_runtime_configuration() -> None:
    if not has_complete_runtime_configuration():
        raise ValueError(
            "Saved runtime configuration is missing. Run main.py and save the country and database connection first."
        )

    country_code = get_current_country_code()
    if not country_code:
        raise ValueError(
            "Saved runtime configuration does not include a country. Run main.py and save it again."
        )

    configure_database_urls_for_country(country_code)


def extract_pager_bounds(page: BeautifulSoup) -> tuple[int, int, int]:
    pager = page.select_one("form#ewpagerform")
    if not pager:
        raise ValueError("Could not find pager on student list page")

    pager_text = pager.get_text(" ", strip=True)
    match = re.search(r"Records\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)", pager_text)
    if not match:
        raise ValueError("Could not parse record count from student list page")

    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def fetch_student_page(browser: Browser, start: int) -> tuple[list[str], int, int]:
    url = f"{BASE_URL}/r_studentviewlist.php?cmd=resetall"
    if start > 1:
        url = f"{url}&start={start}"

    page = BeautifulSoup(browser.fetch(url).text, "lxml")
    first_record, last_record, total_records = extract_pager_bounds(page)
    if first_record != start:
        raise ValueError(f"Student pager expected start {start} but got {first_record}")

    table = page.select_one("table#ewlistmain")
    if not table:
        raise ValueError("Could not find student table on list page")

    student_numbers: list[str] = []
    for row in table.select("tr.ewTableRow, tr.ewTableAltRow"):
        student_number = _extract_student_id_from_row(row)
        if student_number:
            student_numbers.append(student_number)

    return student_numbers, last_record - first_record + 1, total_records


def discover_candidate_students(sample_pages: int) -> list[str]:
    browser = Browser()
    first_page = BeautifulSoup(
        browser.fetch(f"{BASE_URL}/r_studentviewlist.php?cmd=resetall").text, "lxml"
    )
    first_record, last_record, total_records = extract_pager_bounds(first_page)
    page_size = last_record - first_record + 1

    starts = build_page_starts(total_records, page_size, sample_pages)
    candidates: list[str] = []
    seen: set[str] = set()

    for start in starts:
        student_numbers, _, _ = fetch_student_page(browser, start)
        for student_number in student_numbers:
            if student_number in seen:
                continue
            seen.add(student_number)
            candidates.append(student_number)

    return candidates


def profile_candidate(student_number: str) -> CandidateProfile:
    program_ids = extract_student_program_ids(student_number)
    education_ids = extract_student_education_ids(student_number)
    addresses = scrape_student_addresses(student_number)
    semester_count = 0
    module_count = 0

    for program_id in program_ids[:3]:
        semester_ids = extract_student_semester_ids(program_id)
        semester_count += len(semester_ids)
        for semester_id in semester_ids[:3]:
            module_count += len(extract_student_module_ids(semester_id))

    return CandidateProfile(
        student_number=student_number,
        programs=len(program_ids),
        educations=len(education_ids),
        addresses=len(addresses),
        semesters=semester_count,
        modules=module_count,
    )


def reset_student_audit_tables(audit_url: URL) -> None:
    engine = create_engine(audit_url, pool_pre_ping=True)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE "
                "assessment_marks, assessments, registration_clearance, requested_modules, "
                "registration_requests, sponsored_students, student_modules, student_semesters, "
                "clearance, student_programs, student_education, next_of_kins, students, sponsors "
                "RESTART IDENTITY CASCADE"
            )
        )
    engine.dispose()


def reset_catalog_audit_tables(audit_url: URL) -> None:
    engine = create_engine(audit_url, pool_pre_ping=True)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE "
                "semester_modules, structure_semesters, structures, programs, schools, modules "
                "RESTART IDENTITY CASCADE"
            )
        )
    engine.dispose()


def collect_catalog_counts(audit_url: URL) -> dict[str, int]:
    engine = create_engine(audit_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            return {
                "modules": session.query(func.count(Module.id)).scalar() or 0,
                "schools": session.query(func.count(School.id)).scalar() or 0,
                "programs": session.query(func.count(Program.id)).scalar() or 0,
                "structures": session.query(func.count(Structure.id)).scalar() or 0,
                "structure_semesters": session.query(
                    func.count(StructureSemester.id)
                ).scalar()
                or 0,
                "semester_modules": session.query(
                    func.count(SemesterModule.id)
                ).scalar()
                or 0,
            }
    finally:
        engine.dispose()


def import_catalog_data(audit_url: URL) -> dict[str, int | float]:
    patch_database_url(audit_url)

    module_repository = ModuleRepository()
    structure_repository = StructureRepository()
    module_service = ModuleSyncService(module_repository)
    school_service = SchoolSyncService(structure_repository)

    def quiet_progress(*args: Any) -> None:
        return None

    started = time.perf_counter()
    module_service.fetch_and_save_all_modules(quiet_progress)
    school_service.import_all_schools_structures(quiet_progress, fetch_semesters=True)
    duration_seconds = round(time.perf_counter() - started, 3)

    module_repository._engine.dispose()
    structure_repository._engine.dispose()

    counts = collect_catalog_counts(audit_url)
    return {**counts, "duration_seconds": duration_seconds}


def scrape_student_semester_snapshot(
    student_semester_cms_id: str,
    structure_id: int | None,
    repository: StudentRepository,
) -> dict[str, Any]:
    browser = Browser()
    url = f"{BASE_URL}/r_stdsemesterview.php?StdSemesterID={student_semester_cms_id}"
    page = BeautifulSoup(browser.fetch(url).text, "lxml")
    table = page.select_one("table.ewTable")
    if not table:
        return {}

    data: dict[str, Any] = {"cms_id": int(student_semester_cms_id)}

    term = get_table_value(table, "Term")
    if term:
        data["term"] = normalize_text(term)

    semester_str = get_table_value(table, "Semester")
    if semester_str:
        semester_number = parse_semester_number(semester_str)
        if semester_number is not None:
            data["semester_number"] = semester_number
            if structure_id is not None:
                converted_semester = {"F1": "01", "F2": "02"}.get(semester_number)
                structure_semester_id = repository.lookup_structure_semester_id(
                    structure_id, semester_number
                )
                if not structure_semester_id and converted_semester:
                    structure_semester_id = repository.lookup_structure_semester_id(
                        structure_id, converted_semester
                    )
                if not structure_semester_id:
                    repository.refresh_structure_semesters(structure_id)
                    structure_semester_id = repository.lookup_structure_semester_id(
                        structure_id, semester_number
                    )
                    if not structure_semester_id and converted_semester:
                        structure_semester_id = repository.lookup_structure_semester_id(
                            structure_id, converted_semester
                        )
                if structure_semester_id:
                    data["structure_semester_id"] = structure_semester_id

    status = get_table_value(table, "SemStatus")
    if status:
        normalized_status = normalize_semester_status(status)
        if normalized_status:
            data["status"] = normalized_status

    caf_date = get_table_value(table, "CAF Date")
    if caf_date:
        normalized_caf_date = normalize_date(caf_date)
        if normalized_caf_date:
            data["caf_date"] = normalized_caf_date

    sponsor_code = get_table_value(table, "Asst-Provider")
    if sponsor_code:
        normalized_sponsor_code = normalize_text(sponsor_code)
        if normalized_sponsor_code:
            data["sponsor_code"] = normalized_sponsor_code
            sponsor_id = repository.lookup_sponsor(normalized_sponsor_code)
            if sponsor_id is None:
                sponsor_id = repository.create_sponsor(normalized_sponsor_code)
            if sponsor_id:
                data["sponsor_id"] = sponsor_id

    return data


def canonical_student_fields(data: dict[str, Any]) -> dict[str, str]:
    canonical: dict[str, str] = {}
    for field in STUDENT_FIELD_NAMES:
        if field not in data:
            continue
        canonical[field] = normalize_scalar(data[field])
    return canonical


def canonical_contact_rows(rows: Iterable[dict[str, Any]]) -> set[tuple[Any, ...]]:
    merged_rows: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        name = normalize_scalar(row.get("name"))
        relationship = normalize_scalar(row.get("relationship"))
        if not name or not relationship:
            continue
        key = (name, relationship)
        merged = merged_rows.setdefault(
            key,
            {
                "phone": "",
                "email": "",
                "occupation": "",
                "address": "",
                "country": "",
            },
        )
        for field in ("phone", "email", "occupation", "address", "country"):
            value = normalize_scalar(row.get(field))
            if value and not merged[field]:
                merged[field] = value

    return {
        (
            name,
            relationship,
            merged["phone"],
            merged["email"],
            merged["occupation"],
            merged["address"],
            merged["country"],
        )
        for (name, relationship), merged in merged_rows.items()
    }


def canonical_education_rows(rows: Iterable[dict[str, Any]]) -> set[tuple[Any, ...]]:
    canonical: set[tuple[Any, ...]] = set()
    for row in rows:
        cms_id = row.get("cms_id")
        std_no = row.get("std_no")
        school_name = normalize_scalar(row.get("school_name"))
        education_type = normalize_scalar(row.get("type"))
        education_level = normalize_scalar(row.get("level"))
        start_date = normalize_scalar(row.get("start_date"))
        end_date = normalize_scalar(row.get("end_date"))
        if not cms_id or not std_no:
            continue
        if not any(
            (school_name, education_type, education_level, start_date, end_date)
        ):
            continue
        canonical.add(
            (
                int(cms_id),
                normalize_scalar(std_no),
                school_name,
                education_type,
                education_level,
                start_date,
                end_date,
            )
        )
    return canonical


def canonical_program_rows(rows: Iterable[dict[str, Any]]) -> set[tuple[Any, ...]]:
    canonical: set[tuple[Any, ...]] = set()
    for row in rows:
        cms_id = row.get("cms_id")
        std_no = row.get("std_no")
        if not cms_id or not std_no:
            continue
        structure_code = normalize_scalar(
            row.get("resolved_structure_code") or row.get("structure_code")
        )
        canonical.add(
            (
                int(cms_id),
                normalize_scalar(std_no),
                normalize_scalar(row.get("program_code")),
                structure_code,
                normalize_scalar(row.get("reg_date")),
                normalize_scalar(row.get("intake_date")),
                normalize_scalar(row.get("start_term")),
                normalize_scalar(row.get("stream")),
                normalize_scalar(row.get("status")),
                normalize_scalar(row.get("assist_provider")),
                normalize_scalar(row.get("graduation_date")),
            )
        )
    return canonical


def canonical_semester_rows(rows: Iterable[dict[str, Any]]) -> set[tuple[Any, ...]]:
    canonical: set[tuple[Any, ...]] = set()
    for row in rows:
        cms_id = row.get("cms_id")
        student_program_cms_id = row.get("student_program_cms_id")
        if not cms_id or not student_program_cms_id:
            continue
        sponsor_identifier = int(row.get("sponsor_id") or 0)
        canonical.add(
            (
                int(student_program_cms_id),
                int(cms_id),
                normalize_scalar(row.get("term")),
                int(row.get("structure_semester_id") or 0),
                normalize_scalar(row.get("status")),
                normalize_scalar(row.get("caf_date")),
                sponsor_identifier,
            )
        )
    return canonical


def canonical_module_rows(rows: Iterable[dict[str, Any]]) -> set[tuple[Any, ...]]:
    canonical: set[tuple[Any, ...]] = set()
    for row in rows:
        cms_id = row.get("cms_id")
        student_program_cms_id = row.get("student_program_cms_id")
        student_semester_cms_id = row.get("student_semester_cms_id")
        module_code = normalize_scalar(row.get("module_code"))
        if (
            not cms_id
            or not student_program_cms_id
            or not student_semester_cms_id
            or not module_code
        ):
            continue
        canonical.add(
            (
                int(student_program_cms_id),
                int(student_semester_cms_id),
                int(cms_id),
                module_code,
                normalize_scalar(row.get("module_name")),
                normalize_scalar(row.get("type")),
                normalize_float(row.get("credits")),
                normalize_scalar(row.get("status")),
                normalize_scalar(row.get("marks") or "NM"),
                normalize_scalar(row.get("grade") or "NM"),
            )
        )
    return canonical


def scrape_live_snapshot(
    student_number: str, repository: StudentRepository
) -> tuple[dict[str, Any], dict[str, int]]:
    personal_data = scrape_student_personal_view(student_number)
    next_of_kin_rows = personal_data.pop("next_of_kin", [])
    student_data = {**scrape_student_view(student_number), **personal_data}
    address_rows = scrape_student_addresses(student_number)

    education_rows: list[dict[str, Any]] = []
    for education_id in extract_student_education_ids(student_number):
        education_data = scrape_student_education_data(education_id)
        if education_data:
            education_rows.append(education_data)

    program_rows: list[dict[str, Any]] = []
    semester_rows: list[dict[str, Any]] = []
    module_rows: list[dict[str, Any]] = []

    for program_id in extract_student_program_ids(student_number):
        program_data = scrape_student_program_data(program_id)
        if not program_data:
            continue

        structure_code = program_data.get("structure_code")
        structure_id = None
        if structure_code:
            structure_id = repository.resolve_student_program_structure_id(
                str(program_data.get("program_code") or ""),
                str(structure_code),
            )
            if structure_id:
                resolved_structure_code = repository.get_structure_code(structure_id)
                if resolved_structure_code:
                    program_data["resolved_structure_code"] = resolved_structure_code
                repository.preload_structure_semesters(structure_id)

        program_row = {"cms_id": int(program_id), **program_data}
        program_rows.append(program_row)

        for semester_id in extract_student_semester_ids(program_id):
            semester_data = scrape_student_semester_snapshot(
                semester_id, structure_id, repository
            )
            if not semester_data:
                continue

            semester_row = {
                "student_program_cms_id": int(program_id),
                **semester_data,
            }
            semester_rows.append(semester_row)

            for module_id in extract_student_module_ids(semester_id):
                module_data = scrape_student_module_data(module_id, 0)
                if not module_data:
                    continue
                module_rows.append(
                    {
                        "student_program_cms_id": int(program_id),
                        "student_semester_cms_id": int(semester_id),
                        **module_data,
                    }
                )

    snapshot = {
        "student": canonical_student_fields(student_data),
        "contacts": canonical_contact_rows([*next_of_kin_rows, *address_rows]),
        "educations": canonical_education_rows(education_rows),
        "programs": canonical_program_rows(program_rows),
        "semesters": canonical_semester_rows(semester_rows),
        "modules": canonical_module_rows(module_rows),
    }
    live_counts = {
        "contacts": len(snapshot["contacts"]),
        "educations": len(snapshot["educations"]),
        "programs": len(snapshot["programs"]),
        "semesters": len(snapshot["semesters"]),
        "modules": len(snapshot["modules"]),
    }
    return snapshot, live_counts


def collect_db_snapshot(student_number: str, audit_url: URL) -> dict[str, Any]:
    engine = create_engine(audit_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            student = (
                session.query(Student)
                .filter(Student.std_no == int(student_number))
                .first()
            )
            student_data = {
                field: normalize_scalar(getattr(student, field))
                for field in STUDENT_FIELD_NAMES
                if student is not None and getattr(student, field) is not None
            }

            contacts = {
                (
                    normalize_scalar(contact.name),
                    normalize_scalar(contact.relationship),
                    normalize_scalar(contact.phone),
                    normalize_scalar(contact.email),
                    normalize_scalar(contact.occupation),
                    normalize_scalar(contact.address),
                    normalize_scalar(contact.country),
                )
                for contact in session.query(NextOfKin)
                .filter(NextOfKin.std_no == int(student_number))
                .all()
            }

            educations = {
                (
                    int(education.cms_id or 0),
                    normalize_scalar(education.std_no),
                    normalize_scalar(education.school_name),
                    normalize_scalar(education.type),
                    normalize_scalar(education.level),
                    normalize_scalar(education.start_date),
                    normalize_scalar(education.end_date),
                )
                for education in session.query(StudentEducation)
                .filter(StudentEducation.std_no == int(student_number))
                .filter(StudentEducation.cms_id.isnot(None))
                .all()
            }

            programs = {
                (
                    int(student_program.cms_id or 0),
                    normalize_scalar(student_program.std_no),
                    normalize_scalar(program.code),
                    normalize_scalar(structure.code),
                    normalize_scalar(student_program.reg_date),
                    normalize_scalar(student_program.intake_date),
                    normalize_scalar(student_program.start_term),
                    normalize_scalar(student_program.stream),
                    normalize_scalar(student_program.status),
                    normalize_scalar(student_program.assist_provider),
                    normalize_scalar(student_program.graduation_date),
                )
                for student_program, structure, program in session.query(
                    StudentProgram,
                    Structure,
                    Program,
                )
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .join(Program, Structure.program_id == Program.id)
                .filter(StudentProgram.std_no == int(student_number))
                .filter(StudentProgram.cms_id.isnot(None))
                .all()
            }

            semesters = {
                (
                    int(student_program.cms_id or 0),
                    int(student_semester.cms_id or 0),
                    normalize_scalar(student_semester.term_code),
                    int(student_semester.structure_semester_id or 0),
                    normalize_scalar(student_semester.status),
                    normalize_scalar(student_semester.caf_date),
                    int(student_semester.sponsor_id or 0),
                )
                for student_semester, student_program, sponsor in session.query(
                    StudentSemester,
                    StudentProgram,
                    Sponsor,
                )
                .join(
                    StudentProgram,
                    StudentSemester.student_program_id == StudentProgram.id,
                )
                .outerjoin(Sponsor, StudentSemester.sponsor_id == Sponsor.id)
                .filter(StudentProgram.std_no == int(student_number))
                .filter(StudentSemester.cms_id.isnot(None))
                .all()
            }

            modules = {
                (
                    int(student_program.cms_id or 0),
                    int(student_semester.cms_id or 0),
                    int(student_module.cms_id or 0),
                    normalize_scalar(module.code),
                    normalize_scalar(module.name),
                    normalize_scalar(semester_module.type),
                    normalize_float(student_module.credits),
                    normalize_scalar(student_module.status),
                    normalize_scalar(student_module.marks or "NM"),
                    normalize_scalar(student_module.grade or "NM"),
                )
                for student_module, student_semester, student_program, semester_module, module in session.query(
                    StudentModule,
                    StudentSemester,
                    StudentProgram,
                    SemesterModule,
                    Module,
                )
                .join(
                    StudentSemester,
                    StudentModule.student_semester_id == StudentSemester.id,
                )
                .join(
                    StudentProgram,
                    StudentSemester.student_program_id == StudentProgram.id,
                )
                .join(
                    SemesterModule,
                    StudentModule.semester_module_id == SemesterModule.id,
                )
                .join(Module, SemesterModule.module_id == Module.id)
                .filter(StudentProgram.std_no == int(student_number))
                .filter(StudentModule.cms_id.isnot(None))
                .all()
            }

        return {
            "student": student_data,
            "contacts": contacts,
            "educations": educations,
            "programs": programs,
            "semesters": semesters,
            "modules": modules,
        }
    finally:
        engine.dispose()


def compare_snapshots(live: dict[str, Any], db: dict[str, Any]) -> dict[str, Any]:
    mismatches: dict[str, Any] = {}

    student_mismatches: dict[str, dict[str, str]] = {}
    for field, expected_value in live["student"].items():
        actual_value = db["student"].get(field, "")
        if normalize_scalar(expected_value) == normalize_scalar(actual_value):
            continue
        student_mismatches[field] = {
            "expected": normalize_scalar(expected_value),
            "actual": normalize_scalar(actual_value),
        }

    if student_mismatches:
        mismatches["student"] = student_mismatches

    for section in ("contacts", "educations", "programs", "semesters", "modules"):
        if live[section] == db[section]:
            continue
        mismatches[section] = diff_summary(live[section], db[section])

    return mismatches


def audit_student(
    student_number: str,
    service: StudentSyncService,
    repository: StudentRepository,
    audit_url: URL,
) -> AuditStudentResult:
    started = time.perf_counter()
    error: str | None = None

    try:
        live_snapshot, live_counts = scrape_live_snapshot(student_number, repository)
        import_succeeded = service.fetch_student(
            student_number,
            progress_callback=lambda *args: None,
            import_options=IMPORT_OPTIONS,
        )
        db_snapshot = collect_db_snapshot(student_number, audit_url)
        mismatch_details = compare_snapshots(live_snapshot, db_snapshot)
    except Exception as exc:
        import_succeeded = False
        live_counts = {
            "contacts": 0,
            "educations": 0,
            "programs": 0,
            "semesters": 0,
            "modules": 0,
        }
        mismatch_details = {}
        error = str(exc)

    return AuditStudentResult(
        student_number=student_number,
        import_succeeded=import_succeeded,
        mismatch_sections=tuple(sorted(mismatch_details.keys())),
        duration_seconds=round(time.perf_counter() - started, 3),
        live_counts=live_counts,
        mismatch_details=mismatch_details,
        error=error,
    )


def collect_db_counts(audit_url: URL) -> dict[str, int]:
    engine = create_engine(audit_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            return {
                "students": session.query(func.count(Student.std_no)).scalar() or 0,
                "next_of_kins": session.query(func.count(NextOfKin.id)).scalar() or 0,
                "student_education": session.query(
                    func.count(StudentEducation.id)
                ).scalar()
                or 0,
                "student_programs": session.query(
                    func.count(StudentProgram.id)
                ).scalar()
                or 0,
                "student_semesters": session.query(
                    func.count(StudentSemester.id)
                ).scalar()
                or 0,
                "student_modules": session.query(func.count(StudentModule.id)).scalar()
                or 0,
                "sponsors": session.query(func.count(Sponsor.id)).scalar() or 0,
            }
    finally:
        engine.dispose()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="number of students to fully audit after discovery",
    )
    parser.add_argument(
        "--candidate-pages",
        type=int,
        default=18,
        help="number of evenly spaced student list pages to sample for candidate discovery",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=5,
        help="emit progress every N audited students",
    )
    parser.add_argument(
        "--candidate-workers",
        type=int,
        default=8,
        help="concurrent workers for candidate profiling",
    )
    parser.add_argument(
        "--keep-db",
        action="store_true",
        help="keep the temporary audit database instead of dropping it",
    )
    parser.add_argument(
        "--refresh-catalog",
        action="store_true",
        help="truncate the cloned catalog and re-import modules/structures live before auditing students",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.disable(logging.CRITICAL)

    require_runtime_configuration()
    source_url = make_url(get_database_url())
    database_name, audit_url, bootstrap_mode = create_audit_database(source_url)

    try:
        reset_student_audit_tables(audit_url)
        print(
            json.dumps(
                {
                    "event": "audit_database_ready",
                    "country": get_current_country_label(),
                    "country_code": get_current_country_code(),
                    "cms": get_current_cms_base_url(),
                    "source_database": source_url.database,
                    "audit_database": database_name,
                    "bootstrap_mode": bootstrap_mode,
                },
                sort_keys=True,
            ),
            flush=True,
        )

        patch_database_url(audit_url)
        catalog_counts: dict[str, int | float] = {**collect_catalog_counts(audit_url)}
        catalog_mode = "template_clone"
        should_refresh_catalog = args.refresh_catalog or bootstrap_mode == "create_all"
        if not should_refresh_catalog:
            should_refresh_catalog = any(
                catalog_counts[key] == 0
                for key in (
                    "modules",
                    "schools",
                    "programs",
                    "structures",
                    "structure_semesters",
                    "semester_modules",
                )
            )

        if should_refresh_catalog:
            reset_catalog_audit_tables(audit_url)
            catalog_counts = import_catalog_data(audit_url)
            catalog_mode = "refreshed_live"
        else:
            catalog_counts = {**catalog_counts, "duration_seconds": 0.0}

        print(
            json.dumps(
                {
                    "event": "catalog_ready",
                    "catalog_mode": catalog_mode,
                    **catalog_counts,
                },
                sort_keys=True,
            ),
            flush=True,
        )

        candidate_numbers = discover_candidate_students(args.candidate_pages)
        candidate_profiles: list[CandidateProfile] = []
        with ThreadPoolExecutor(max_workers=max(args.candidate_workers, 1)) as executor:
            future_to_student = {
                executor.submit(profile_candidate, student_number): student_number
                for student_number in candidate_numbers
            }
            for future in as_completed(future_to_student):
                candidate_profiles.append(future.result())

        selected_candidates = select_audit_students(candidate_profiles, args.limit)
        selected_students = [
            candidate.student_number for candidate in selected_candidates
        ]

        print(
            json.dumps(
                {
                    "event": "student_selection_complete",
                    "candidate_count": len(candidate_profiles),
                    "selected_count": len(selected_students),
                    "selected_students": selected_students[:20],
                    "richest_candidates": [
                        {
                            "student_number": candidate.student_number,
                            "programs": candidate.programs,
                            "educations": candidate.educations,
                            "addresses": candidate.addresses,
                            "semesters": candidate.semesters,
                            "modules": candidate.modules,
                        }
                        for candidate in sorted(
                            candidate_profiles,
                            key=lambda item: item.score,
                            reverse=True,
                        )[:10]
                    ],
                },
                sort_keys=True,
            ),
            flush=True,
        )

        patch_database_url(audit_url)
        repository = StudentRepository()
        service = StudentSyncService(repository)

        results: list[AuditStudentResult] = []
        started = time.perf_counter()

        for index, student_number in enumerate(selected_students, start=1):
            result = audit_student(student_number, service, repository, audit_url)
            results.append(result)

            if index % max(args.progress_every, 1) == 0 or index == len(
                selected_students
            ):
                print(
                    json.dumps(
                        {
                            "event": "student_audit_progress",
                            "processed": index,
                            "total": len(selected_students),
                            "import_failures": sum(
                                1 for item in results if not item.import_succeeded
                            ),
                            "comparison_failures": sum(
                                1 for item in results if item.mismatch_sections
                            ),
                            "elapsed_seconds": round(time.perf_counter() - started, 3),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )

        db_counts = collect_db_counts(audit_url)
        durations = [result.duration_seconds for result in results]
        import_failures = [result for result in results if not result.import_succeeded]
        comparison_failures = [result for result in results if result.mismatch_sections]

        summary = {
            "event": "final_summary",
            "status": (
                "pass" if not import_failures and not comparison_failures else "fail"
            ),
            "country": get_current_country_label(),
            "country_code": get_current_country_code(),
            "cms": get_current_cms_base_url(),
            "source_database": source_url.database,
            "audit_database": database_name,
            "bootstrap_mode": bootstrap_mode,
            "catalog_counts": catalog_counts,
            "catalog_mode": catalog_mode,
            "selection": {
                "candidate_pages": args.candidate_pages,
                "candidate_count": len(candidate_profiles),
                "audited_students": len(results),
            },
            "student_results": {
                "audited": len(results),
                "import_failures": len(import_failures),
                "comparison_failures": len(comparison_failures),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "average_seconds": (
                    round(statistics.fmean(durations), 3) if durations else 0.0
                ),
                "median_seconds": (
                    round(statistics.median(durations), 3) if durations else 0.0
                ),
                "slowest_seconds": round(max(durations), 3) if durations else 0.0,
                "with_contacts": sum(
                    1 for result in results if result.live_counts["contacts"] > 0
                ),
                "with_educations": sum(
                    1 for result in results if result.live_counts["educations"] > 0
                ),
                "with_programs": sum(
                    1 for result in results if result.live_counts["programs"] > 0
                ),
                "with_semesters": sum(
                    1 for result in results if result.live_counts["semesters"] > 0
                ),
                "with_modules": sum(
                    1 for result in results if result.live_counts["modules"] > 0
                ),
            },
            "db_counts": db_counts,
            "failure_samples": [
                {
                    "student_number": result.student_number,
                    "import_succeeded": result.import_succeeded,
                    "mismatch_sections": list(result.mismatch_sections),
                    "live_counts": result.live_counts,
                    "duration_seconds": result.duration_seconds,
                    "error": result.error,
                    "mismatch_details": result.mismatch_details,
                }
                for result in [*import_failures, *comparison_failures][:10]
            ],
        }
        print(json.dumps(summary, sort_keys=True), flush=True)
    finally:
        if not args.keep_db:
            drop_audit_database(source_url, database_name)


if __name__ == "__main__":
    main()
