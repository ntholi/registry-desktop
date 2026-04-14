from __future__ import annotations

import datetime
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, cast

from sqlalchemy import String, distinct, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from base import get_logger
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
    Term,
    get_engine,
)
from utils.normalizers import normalize_student_module_status

logger = get_logger(__name__)

_structure_semester_cache: dict[tuple[int, str], Optional[int]] = {}
_sponsor_code_cache: dict[str, Optional[int]] = {}
_sponsor_name_cache: dict[str, Optional[int]] = {}


def _coerce_datetime(value: object) -> datetime.datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime.datetime):
        return value

    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time.min)

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None

        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"

        try:
            return datetime.datetime.fromisoformat(normalized)
        except ValueError:
            return None

    return None


def _coerce_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None

        try:
            return int(normalized)
        except ValueError:
            return None

    return None


def _normalize_sponsor_key(value: str | None) -> Optional[str]:
    if not value or not value.strip():
        return None
    return value.strip()


def _extract_structure_period_prefixes(*values: str | None) -> list[str]:
    prefixes: list[str] = []

    for value in values:
        normalized = (value or "").strip()
        if len(normalized) < 7:
            continue

        year = normalized[:4]
        separator = normalized[4]
        month = normalized[5:7]
        if not year.isdigit() or not month.isdigit() or separator != "-":
            continue

        prefix = f"{year[2:]}{month}"
        if prefix not in prefixes:
            prefixes.append(prefix)

    return prefixes


def _cache_sponsor(
    sponsor_id: Optional[int],
    *,
    sponsor_code: str | None = None,
    sponsor_name: str | None = None,
) -> None:
    normalized_code = _normalize_sponsor_key(sponsor_code)
    normalized_name = _normalize_sponsor_key(sponsor_name)

    if normalized_code:
        _sponsor_code_cache[normalized_code] = sponsor_id
    if normalized_name:
        _sponsor_name_cache[normalized_name] = sponsor_id


@dataclass(frozen=True)
class StudentRow:
    std_no: str
    name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[str]
    faculty_code: Optional[str]
    program_name: Optional[str]
    phone1: Optional[str]


class StudentRepository:
    def __init__(self) -> None:
        self._engine = get_engine()
        self._refreshed_structure_semesters: set[int] = set()

    @contextmanager
    def _session(self):
        with Session(self._engine) as session:
            yield session

    def list_active_schools(self):
        with self._session() as session:
            return (
                session.query(School.cms_id.label("cms_id"), School.name)
                .filter(School.is_active == True)
                .filter(School.cms_id.isnot(None))
                .order_by(School.name)
                .all()
            )

    def list_programs(self, school_cms_id: Optional[int] = None):
        with self._session() as session:
            query = session.query(Program.cms_id.label("cms_id"), Program.name).filter(
                Program.cms_id.isnot(None)
            )
            if school_cms_id:
                query = query.join(School, Program.school_id == School.id).filter(
                    School.cms_id == school_cms_id
                )
            return query.order_by(Program.name).all()

    def list_terms(self):
        with self._session() as session:
            rows = (
                session.query(distinct(StudentSemester.term_code))
                .filter(StudentSemester.term_code.isnot(None))
                .order_by(StudentSemester.term_code.desc())
                .all()
            )
            return [row[0] for row in rows]

    def list_semesters(self):
        with self._session() as session:
            from database import StructureSemester

            rows = (
                session.query(distinct(StructureSemester.semester_number))
                .join(
                    StudentSemester,
                    StudentSemester.structure_semester_id == StructureSemester.id,
                )
                .order_by(StructureSemester.semester_number)
                .all()
            )
            return [row[0] for row in rows]

    def fetch_students(
        self,
        *,
        school_cms_id: Optional[int] = None,
        program_cms_id: Optional[int] = None,
        term: Optional[str] = None,
        semester_number: Optional[str] = None,
        search_query: str = "",
        page: int = 1,
        page_size: int = 30,
    ):
        offset = (page - 1) * page_size
        with self._session() as session:
            query = (
                session.query(
                    Student.std_no,
                    Student.name,
                    Student.gender,
                    Student.date_of_birth,
                    School.code.label("faculty_code"),
                    Program.name.label("program_name"),
                    Student.phone1,
                )
                .outerjoin(
                    StudentProgram,
                    (Student.std_no == StudentProgram.std_no)
                    & (StudentProgram.status == "Active"),
                )
                .outerjoin(Structure, StudentProgram.structure_id == Structure.id)
                .outerjoin(Program, Structure.program_id == Program.id)
                .outerjoin(School, Program.school_id == School.id)
                .distinct()
            )

            if school_cms_id:
                query = query.filter(School.cms_id == school_cms_id)

            if program_cms_id:
                query = query.filter(Program.cms_id == program_cms_id)

            if term or semester_number:
                from database import StructureSemester

                query = query.join(
                    StudentSemester,
                    StudentProgram.id == StudentSemester.student_program_id,
                )
                if semester_number:
                    query = query.join(
                        StructureSemester,
                        StudentSemester.structure_semester_id == StructureSemester.id,
                    )
                    query = query.filter(
                        StructureSemester.semester_number == semester_number
                    )
                if term:
                    query = query.filter(StudentSemester.term_code == term)

            if search_query:
                search_term = f"%{search_query}%"
                query = query.filter(
                    or_(
                        Student.std_no.cast(String).like(search_term),
                        Student.name.like(search_term),
                        Student.national_id.like(search_term),
                    )
                )

            query = query.order_by(Student.std_no.desc())
            total = query.count()
            results = query.offset(offset).limit(page_size).all()

        rows = [
            StudentRow(
                std_no=str(result.std_no),
                name=result.name,
                gender=result.gender,
                date_of_birth=result.date_of_birth,
                faculty_code=result.faculty_code,
                program_name=result.program_name,
                phone1=result.phone1,
            )
            for result in results
        ]
        return rows, total

    def get_student_programs(self, student_number: str):
        try:
            numeric_student_number = int(student_number)
        except (TypeError, ValueError):
            return []

        with self._session() as session:
            programs = (
                session.query(
                    StudentProgram.id.label("student_program_db_id"),
                    StudentProgram.cms_id.label("student_program_cms_id"),
                    StudentProgram.intake_date,
                    StudentProgram.reg_date,
                    StudentProgram.start_term,
                    StudentProgram.status,
                    StudentProgram.stream,
                    StudentProgram.graduation_date,
                    Structure.id.label("structure_db_id"),
                    Structure.cms_id.label("structure_cms_id"),
                    Program.name.label("program_name"),
                    Program.code.label("program_code"),
                    Program.cms_id.label("program_cms_id"),
                    School.name.label("school_name"),
                    School.cms_id.label("school_cms_id"),
                )
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .join(Program, Structure.program_id == Program.id)
                .join(School, Program.school_id == School.id)
                .filter(StudentProgram.std_no == numeric_student_number)
                .order_by(StudentProgram.id.desc())
                .all()
            )

            return programs

    def get_student_program_details(self, student_number: str):
        try:
            numeric_student_number = int(student_number)
        except (TypeError, ValueError):
            return None

        with self._session() as session:
            program_details = (
                session.query(
                    StudentProgram.id.label("student_program_db_id"),
                    StudentProgram.cms_id.label("student_program_cms_id"),
                    StudentProgram.intake_date,
                    StudentProgram.start_term,
                    Structure.id.label("structure_db_id"),
                    Structure.cms_id.label("structure_cms_id"),
                    Program.cms_id.label("program_cms_id"),
                    School.cms_id.label("school_cms_id"),
                )
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .join(Program, Structure.program_id == Program.id)
                .join(School, Program.school_id == School.id)
                .filter(StudentProgram.std_no == numeric_student_number)
                .filter(
                    or_(
                        StudentProgram.status == "Active",
                        StudentProgram.status == "Completed",
                    )
                )
                .order_by(StudentProgram.id)
                .first()
            )

            if not program_details:
                return None

            return {
                "student_program_db_id": program_details.student_program_db_id,
                "student_program_cms_id": program_details.student_program_cms_id,
                "intake_date": program_details.intake_date,
                "start_term": program_details.start_term,
                "structure_db_id": program_details.structure_db_id,
                "structure_cms_id": program_details.structure_cms_id,
                "program_cms_id": program_details.program_cms_id,
                "school_cms_id": program_details.school_cms_id,
            }

    def get_student_program_details_by_id(self, student_program_db_id: int):
        with self._session() as session:
            program_details = (
                session.query(
                    StudentProgram.id.label("student_program_db_id"),
                    StudentProgram.cms_id.label("student_program_cms_id"),
                    StudentProgram.std_no,
                    StudentProgram.intake_date,
                    StudentProgram.start_term,
                    Structure.id.label("structure_db_id"),
                    Structure.cms_id.label("structure_cms_id"),
                    Program.cms_id.label("program_cms_id"),
                    School.cms_id.label("school_cms_id"),
                )
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .join(Program, Structure.program_id == Program.id)
                .join(School, Program.school_id == School.id)
                .filter(StudentProgram.id == student_program_db_id)
                .first()
            )

            if not program_details:
                return None

            return {
                "student_program_db_id": program_details.student_program_db_id,
                "student_program_cms_id": program_details.student_program_cms_id,
                "std_no": program_details.std_no,
                "intake_date": program_details.intake_date,
                "start_term": program_details.start_term,
                "structure_db_id": program_details.structure_db_id,
                "structure_cms_id": program_details.structure_cms_id,
                "program_cms_id": program_details.program_cms_id,
                "school_cms_id": program_details.school_cms_id,
            }

    def get_structure_semesters(self, structure_db_id: int):
        with self._session() as session:
            from database import StructureSemester

            semesters = (
                session.query(
                    StructureSemester.id.label("structure_semester_db_id"),
                    StructureSemester.cms_id.label("structure_semester_cms_id"),
                    StructureSemester.semester_number,
                    StructureSemester.name,
                )
                .filter(StructureSemester.structure_id == structure_db_id)
                .filter(StructureSemester.cms_id.isnot(None))
                .order_by(StructureSemester.semester_number)
                .all()
            )
            return semesters

    def get_structure_semester_number(self, structure_semester_id: int):
        with self._session() as session:
            from database import StructureSemester

            semester = (
                session.query(StructureSemester.semester_number)
                .filter(StructureSemester.id == structure_semester_id)
                .first()
            )
            return semester[0] if semester else None

    def update_student(self, student_number: str, data: dict):
        try:
            numeric_student_number = int(student_number)
        except (TypeError, ValueError):
            return False

        with self._session() as session:
            student = (
                session.query(Student)
                .filter(Student.std_no == numeric_student_number)
                .first()
            )

            if not student:
                student = Student(
                    std_no=numeric_student_number,
                    name=data.get("name") or "",
                    national_id=data.get("national_id") or "",
                    status=data.get("status") or "Active",
                )
                session.add(student)

            for key, value in data.items():
                if value is None or not hasattr(student, key):
                    continue

                if key == "date_of_birth":
                    value = _coerce_datetime(value)
                    if value is None:
                        continue

                setattr(student, key, value)

            session.commit()
            return True

    def get_structure_by_code_or_desc(self, code: str, desc: str) -> Optional[int]:
        with self._session() as session:
            structure = (
                session.query(Structure.id).filter(Structure.code == code).first()
            )
            if structure:
                return structure[0]

            structure = (
                session.query(Structure.id).filter(Structure.desc == desc).first()
            )
            if structure:
                return structure[0]

            if code.isdigit():
                structure = (
                    session.query(Structure.id)
                    .filter(Structure.cms_id == int(code))
                    .first()
                )
                if structure:
                    return structure[0]

            return None

    def resolve_student_program_structure_id(
        self,
        program_code: str | None,
        structure_identifier: str | None,
        start_term: str | None = None,
        intake_date: str | None = None,
        reg_date: str | None = None,
    ) -> Optional[int]:
        normalized_program_code = (program_code or "").strip()
        normalized_identifier = (structure_identifier or "").strip()

        if normalized_program_code:
            with self._session() as session:
                scoped_query = session.query(
                    Structure.id,
                    Structure.code,
                    Structure.desc,
                    Structure.cms_id,
                ).join(
                    Program, Structure.program_id == Program.id
                )
                scoped_query = scoped_query.filter(
                    Program.code == normalized_program_code
                )

                if normalized_identifier:
                    structure = scoped_query.filter(
                        Structure.code == normalized_identifier
                    ).first()
                    if structure:
                        return structure[0]

                    structure = scoped_query.filter(
                        Structure.desc == normalized_identifier
                    ).first()
                    if structure:
                        return structure[0]

                    if normalized_identifier.isdigit():
                        structure = scoped_query.filter(
                            Structure.cms_id == int(normalized_identifier)
                        ).first()
                        if structure:
                            return structure[0]

                for prefix in _extract_structure_period_prefixes(
                    start_term,
                    intake_date,
                    reg_date,
                ):
                    candidates = scoped_query.filter(
                        or_(
                            Structure.code.like(f"{prefix}-%"),
                            Structure.desc.like(f"{prefix}-%"),
                            Structure.code.like(f"{prefix}%"),
                            Structure.desc.like(f"{prefix}%"),
                        )
                    ).all()
                    if not candidates:
                        continue

                    expected_code = f"{prefix}-{normalized_program_code}"
                    exact_candidates = [
                        candidate
                        for candidate in candidates
                        if str(candidate.code or "").rstrip(".") == expected_code
                        or str(candidate.desc or "").rstrip(".") == expected_code
                    ]
                    if len(exact_candidates) == 1:
                        return exact_candidates[0][0]
                    if len(candidates) == 1:
                        return candidates[0][0]

        if not normalized_identifier:
            return None

        return self.get_structure_by_code_or_desc(
            normalized_identifier, normalized_identifier
        )

    def get_structure_cms_id(self, structure_id: int) -> Optional[int]:
        with self._session() as session:
            result = (
                session.query(Structure.cms_id)
                .filter(Structure.id == structure_id)
                .first()
            )
            return result[0] if result else None

    def get_structure_code(self, structure_id: int) -> Optional[str]:
        with self._session() as session:
            result = (
                session.query(Structure.code)
                .filter(Structure.id == structure_id)
                .first()
            )
            return result[0] if result else None

    def refresh_structure_semesters(self, structure_id: int) -> int:
        if structure_id in self._refreshed_structure_semesters:
            return 0

        structure_cms_id = self.get_structure_cms_id(structure_id)
        self._refreshed_structure_semesters.add(structure_id)

        if not structure_cms_id:
            return 0

        from features.sync.structures.repository import StructureRepository
        from features.sync.structures.scraper import scrape_semesters

        semesters = scrape_semesters(structure_cms_id)
        structure_repository = StructureRepository()

        for semester in semesters:
            structure_repository.save_semester(
                int(semester["cms_id"]),
                str(semester["semester_number"]),
                str(semester["name"]),
                float(semester["total_credits"]),
                structure_id,
            )

        self.preload_structure_semesters(structure_id)
        return len(semesters)

    def get_student_semesters(self, student_program_db_id: int):
        with self._session() as session:
            from database import StructureSemester

            semesters = (
                session.query(
                    StudentSemester.id.label("student_semester_db_id"),
                    StudentSemester.cms_id.label("student_semester_cms_id"),
                    StudentSemester.term_code,
                    StructureSemester.id.label("structure_semester_db_id"),
                    StructureSemester.cms_id.label("structure_semester_cms_id"),
                    StructureSemester.semester_number,
                    StudentSemester.status,
                    StudentSemester.caf_date,
                )
                .join(
                    StructureSemester,
                    StudentSemester.structure_semester_id == StructureSemester.id,
                )
                .filter(StudentSemester.student_program_id == student_program_db_id)
                .order_by(StudentSemester.term_code, StructureSemester.semester_number)
                .all()
            )
            return semesters

    def get_student_semester_by_id(self, student_semester_db_id: int):
        with self._session() as session:
            from database import StructureSemester

            result = (
                session.query(
                    StudentSemester.id.label("student_semester_db_id"),
                    StudentSemester.student_program_id.label("student_program_db_id"),
                    StudentProgram.cms_id.label("student_program_cms_id"),
                    StudentSemester.term_code,
                    StudentSemester.structure_semester_id.label(
                        "structure_semester_db_id"
                    ),
                    StructureSemester.cms_id.label("structure_semester_cms_id"),
                    StructureSemester.semester_number,
                    StudentSemester.status,
                    StudentSemester.caf_date,
                    StudentProgram.structure_id.label("structure_db_id"),
                    Structure.cms_id.label("structure_cms_id"),
                    StudentSemester.cms_id.label("student_semester_cms_id"),
                )
                .join(
                    StudentProgram,
                    StudentSemester.student_program_id == StudentProgram.id,
                )
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .join(
                    StructureSemester,
                    StudentSemester.structure_semester_id == StructureSemester.id,
                )
                .filter(StudentSemester.id == student_semester_db_id)
                .first()
            )
            if result:
                return {
                    "student_semester_db_id": result.student_semester_db_id,
                    "student_semester_cms_id": result.student_semester_cms_id,
                    "student_program_db_id": result.student_program_db_id,
                    "student_program_cms_id": result.student_program_cms_id,
                    "term_code": result.term_code,
                    "structure_semester_db_id": result.structure_semester_db_id,
                    "structure_semester_cms_id": result.structure_semester_cms_id,
                    "semester_number": result.semester_number,
                    "status": result.status,
                    "caf_date": result.caf_date,
                    "structure_db_id": result.structure_db_id,
                    "structure_cms_id": result.structure_cms_id,
                }
            return None

    def get_semester_modules(self, student_semester_db_id: int):
        with self._session() as session:
            modules = (
                session.query(
                    StudentModule.id.label("student_module_db_id"),
                    StudentModule.cms_id.label("student_module_cms_id"),
                    SemesterModule.id.label("semester_module_db_id"),
                    SemesterModule.cms_id.label("semester_module_cms_id"),
                    Module.code.label("module_code"),
                    Module.name.label("module_name"),
                    StudentModule.status,
                    StudentModule.marks,
                    StudentModule.grade,
                    StudentModule.credits,
                )
                .join(
                    SemesterModule,
                    StudentModule.semester_module_id == SemesterModule.id,
                )
                .join(Module, SemesterModule.module_id == Module.id)
                .filter(StudentModule.student_semester_id == student_semester_db_id)
                .order_by(Module.code)
                .all()
            )
            return modules

    def search_semester_modules(self, search_query: str):
        with self._session() as session:
            from database import StructureSemester

            search_pattern = f"%{search_query}%"

            results = (
                session.query(
                    SemesterModule.id.label("semester_module_db_id"),
                    SemesterModule.cms_id.label("semester_module_cms_id"),
                    Module.code.label("module_code"),
                    Module.name.label("module_name"),
                    Program.name.label("program_name"),
                    SemesterModule.credits,
                    StructureSemester.semester_number,
                )
                .join(Module, SemesterModule.module_id == Module.id)
                .join(
                    StructureSemester,
                    SemesterModule.semester_id == StructureSemester.id,
                )
                .join(Structure, StructureSemester.structure_id == Structure.id)
                .join(Program, Structure.program_id == Program.id)
                .filter(
                    or_(
                        Module.code.like(search_pattern),
                        Module.name.like(search_pattern),
                    )
                )
                .filter(SemesterModule.cms_id.isnot(None))
                .order_by(Module.code, Program.name)
                .all()
            )

            return [
                {
                    "semester_module_db_id": r.semester_module_db_id,
                    "semester_module_cms_id": r.semester_module_cms_id,
                    "module_code": r.module_code,
                    "module_name": r.module_name,
                    "program_name": r.program_name,
                    "credits": r.credits,
                    "semester_number": r.semester_number,
                }
                for r in results
            ]

    def upsert_student_program(
        self, student_program_id: str, std_no: int, data: dict
    ) -> tuple[bool, str, Optional[int]]:
        structure_id: Optional[int] = None
        with self._session() as session:
            try:
                existing = (
                    session.query(StudentProgram)
                    .filter(StudentProgram.std_no == std_no)
                    .filter(StudentProgram.cms_id == int(student_program_id))
                    .first()
                )

                if "structure_code" in data:
                    structure_id = self.resolve_student_program_structure_id(
                        data.get("program_code"),
                        data["structure_code"],
                        data.get("start_term"),
                        data.get("intake_date"),
                        data.get("reg_date"),
                    )
                    if not structure_id:
                        logger.error(
                            f"Structure not found - std_no={std_no}, "
                            f"student_program_id={student_program_id}, "
                            f"structure_code={data['structure_code']}"
                        )
                elif any(
                    data.get(key) for key in ("start_term", "intake_date", "reg_date")
                ):
                    structure_id = self.resolve_student_program_structure_id(
                        data.get("program_code"),
                        None,
                        data.get("start_term"),
                        data.get("intake_date"),
                        data.get("reg_date"),
                    )

                if existing:
                    existing.cms_id = int(student_program_id)  # type: ignore
                    if structure_id:
                        existing.structure_id = structure_id  # type: ignore
                    if "reg_date" in data:
                        existing.reg_date = data["reg_date"]
                    if "intake_date" in data:
                        existing.intake_date = data["intake_date"]
                    if "start_term" in data:
                        existing.start_term = data["start_term"]
                    if "stream" in data:
                        existing.stream = data["stream"]
                    if "status" in data:
                        existing.status = data["status"]
                    if "assist_provider" in data:
                        existing.assist_provider = data["assist_provider"]
                    if "graduation_date" in data:
                        existing.graduation_date = data["graduation_date"]

                    session.commit()
                    logger.info(
                        f"Updated student program {student_program_id} for student {std_no}"
                    )
                    return True, "Student program updated", cast(int, existing.id)
                else:
                    if not structure_id:
                        logger.error(
                            f"Cannot create student program without valid structure - "
                            f"std_no={std_no}, student_program_id={student_program_id}, "
                            f"structure_code={data.get('structure_code')}, data={data}"
                        )
                        return False, "Structure not found", None

                    new_program = StudentProgram(
                        cms_id=int(student_program_id),
                        std_no=std_no,
                        structure_id=structure_id,
                        reg_date=data.get("reg_date"),
                        intake_date=data.get("intake_date"),
                        start_term=data.get("start_term"),
                        stream=data.get("stream"),
                        status=data.get("status", "Active"),
                        assist_provider=data.get("assist_provider"),
                        graduation_date=data.get("graduation_date"),
                    )
                    session.add(new_program)
                    session.commit()
                    session.refresh(new_program)
                    logger.info(
                        f"Created student program {student_program_id} for student {std_no}"
                    )
                    return True, "Student program created", cast(int, new_program.id)

            except Exception as e:
                session.rollback()
                error_msg = f"Error upserting student program: {str(e)}"
                logger.error(
                    f"Error upserting student program - std_no={std_no}, "
                    f"student_program_id={student_program_id}, "
                    f"structure_id={structure_id}, error={str(e)}, data={data}",
                )
                return False, error_msg, None

    def upsert_student_semester(
        self, std_program_id: int, data: dict
    ) -> tuple[bool, str, Optional[int]]:
        semester_id: Optional[int] = None
        with self._session() as session:
            try:
                if "cms_id" in data:
                    try:
                        semester_id = int(data["cms_id"])
                    except (TypeError, ValueError):
                        logger.error(
                            f"Invalid semester ID - std_program_id={std_program_id}, "
                            f"semester_id={data.get('cms_id')}, data={data}"
                        )

                existing = None
                if semester_id:
                    existing = (
                        session.query(StudentSemester)
                        .filter(StudentSemester.cms_id == semester_id)
                        .first()
                    )

                if not existing:
                    existing_query = session.query(StudentSemester).filter(
                        StudentSemester.student_program_id == std_program_id,
                        StudentSemester.cms_id.is_(None),
                    )
                    if data.get("term"):
                        existing_query = existing_query.filter(
                            StudentSemester.term_code == data.get("term")
                        )
                    if data.get("structure_semester_id"):
                        existing_query = existing_query.filter(
                            StudentSemester.structure_semester_id
                            == data.get("structure_semester_id")
                        )
                    existing = existing_query.first()

                if existing:
                    if semester_id:
                        existing.cms_id = semester_id  # type: ignore
                    if "structure_semester_id" in data:
                        existing.structure_semester_id = data["structure_semester_id"]
                    if "status" in data:
                        existing.status = data["status"]
                    if "semester_status" in data:
                        existing.status = data["semester_status"]
                    if "caf_date" in data:
                        existing.caf_date = data["caf_date"]
                    if "sponsor_id" in data:
                        existing.sponsor_id = data["sponsor_id"]

                    session.commit()
                    logger.info(
                        f"Updated student semester {existing.id} for program {std_program_id}"
                    )
                    return True, "Student semester updated", cast(int, existing.id)
                else:
                    if not semester_id:
                        error_msg = "Cannot create student semester without ID from CMS"
                        logger.error(
                            f"Cannot create student semester without ID - "
                            f"std_program_id={std_program_id}, data={data}"
                        )
                        return False, error_msg, None

                    if "structure_semester_id" not in data:
                        error_msg = f"Cannot create student semester without structure_semester_id for std_program_id {std_program_id}"
                        logger.error(
                            f"Cannot create student semester without structure_semester_id - "
                            f"std_program_id={std_program_id}, semester_id={semester_id}, "
                            f"term={data.get('term')}, data={data}"
                        )
                        return False, error_msg, None

                    new_semester = StudentSemester(
                        cms_id=semester_id,
                        student_program_id=std_program_id,
                        term_code=data.get("term"),
                        structure_semester_id=data["structure_semester_id"],
                        status=data.get("status")
                        or data.get("semester_status", "Active"),
                        caf_date=data.get("caf_date"),
                        sponsor_id=data.get("sponsor_id"),
                    )
                    session.add(new_semester)
                    session.commit()
                    session.refresh(new_semester)
                    logger.info(
                        f"Created student semester {semester_id} for program {std_program_id}"
                    )
                    return True, "Student semester created", cast(int, new_semester.id)

            except Exception as e:
                session.rollback()
                error_msg = f"Error upserting student semester: {str(e)}"
                logger.error(
                    f"Error upserting student semester - std_program_id={std_program_id}, "
                    f"semester_id={semester_id}, term={data.get('term')}, "
                    f"structure_semester_id={data.get('structure_semester_id')}, "
                    f"error={str(e)}, data={data}",
                )
                return False, error_msg, None

    def _create_missing_semester_module(
        self,
        session: Session,
        module_code: str,
        module_name: str,
        module_type: str,
        credits: float,
        structure_semester_id: int,
    ) -> Optional[int]:
        module = session.query(Module).filter(Module.code == module_code).first()
        if not module:
            module = Module(code=module_code, name=module_name, status="Active")
            session.add(module)
            session.flush()
            logger.warn(f"Auto-created module - code={module_code}, name={module_name}")

        sem_module = SemesterModule(
            module_id=module.id,
            type=module_type,
            credits=credits,
            semester_id=structure_semester_id,
        )
        session.add(sem_module)
        session.flush()
        logger.warn(
            f"Auto-created semester module - module_code={module_code}, "
            f"structure_semester_id={structure_semester_id}, "
            f"semester_module_id={sem_module.id}"
        )
        return sem_module.id

    def _lookup_semester_module_for_student_semester(
        self,
        session: Session,
        *,
        module_code: str,
        structure_semester_id: int,
        module_type: str | None = None,
        credits: float | None = None,
    ) -> Optional[int]:
        candidates = (
            session.query(
                SemesterModule.id,
                SemesterModule.type,
                SemesterModule.credits,
            )
            .join(Module, SemesterModule.module_id == Module.id)
            .filter(Module.code == module_code)
            .filter(SemesterModule.semester_id == structure_semester_id)
            .all()
        )

        if not candidates:
            return None

        target_type = (module_type or "").strip()
        target_credits = float(credits) if credits is not None else None

        if target_type:
            type_matches = [
                candidate for candidate in candidates if candidate.type == target_type
            ]
            if target_credits is not None:
                for candidate in type_matches:
                    if abs(float(candidate.credits or 0) - target_credits) < 1e-6:
                        return candidate.id
                return None
            if type_matches:
                return type_matches[0].id
            return None

        if target_credits is not None:
            for candidate in candidates:
                if abs(float(candidate.credits or 0) - target_credits) < 1e-6:
                    return candidate.id
            return None

        if len(candidates) == 1:
            return candidates[0].id

        return None

    def get_semester_module_by_code(
        self, module_code: str, structure_id: int
    ) -> Optional[int]:
        with self._session() as session:
            semester_module = (
                session.query(SemesterModule.id)
                .join(Module, SemesterModule.module_id == Module.id)
                .join(
                    StructureSemester,
                    SemesterModule.semester_id == StructureSemester.id,
                )
                .filter(Module.code == module_code)
                .filter(StructureSemester.structure_id == structure_id)
                .first()
            )
            if semester_module:
                return semester_module[0]

            semester_module = (
                session.query(SemesterModule.id)
                .join(Module, SemesterModule.module_id == Module.id)
                .filter(Module.code == module_code)
                .first()
            )
            if semester_module:
                logger.warning(
                    f"Found semester module in another structure - "
                    f"module_code={module_code}, structure_id={structure_id}, "
                    f"will auto-create in correct structure"
                )
                return None

            return None

    def get_semester_module_credits_by_cms_id(
        self, semester_module_cms_id: int
    ) -> Optional[float]:
        with self._session() as session:
            semester_module = (
                session.query(SemesterModule.credits)
                .filter(SemesterModule.cms_id == semester_module_cms_id)
                .first()
            )
            return semester_module[0] if semester_module else None

    def get_semester_module_db_id_by_cms_id(
        self, semester_module_cms_id: int
    ) -> Optional[int]:
        with self._session() as session:
            semester_module = (
                session.query(SemesterModule.id)
                .filter(SemesterModule.cms_id == semester_module_cms_id)
                .first()
            )
            return semester_module[0] if semester_module else None

    def upsert_student_module(self, data: dict) -> tuple[bool, str]:
        std_module_id: int = 0
        student_semester_db_id: Optional[int] = None
        semester_module_id: Optional[int] = None
        with self._session() as session:
            try:
                std_module_id = int(data["cms_id"])
                student_semester_db_id = data.get("student_semester_db_id") or data.get(
                    "student_semester_id"
                )

                if not student_semester_db_id:
                    return False, "Missing student_semester_id"

                existing = (
                    session.query(StudentModule)
                    .filter(StudentModule.cms_id == std_module_id)
                    .first()
                )

                if "semester_module_cms_id" in data and data["semester_module_cms_id"]:
                    semester_module_id = self.get_semester_module_db_id_by_cms_id(
                        int(data["semester_module_cms_id"])
                    )
                elif "semester_module_id" in data and data["semester_module_id"]:
                    semester_module_id = data["semester_module_id"]
                elif "module_code" in data:
                    student_semester = (
                        session.query(StudentSemester)
                        .filter(StudentSemester.id == student_semester_db_id)
                        .first()
                    )

                    if student_semester is not None:
                        student_program_id = cast(
                            int, student_semester.student_program_id
                        )
                        student_program = (
                            session.query(StudentProgram)
                            .filter(StudentProgram.id == student_program_id)
                            .first()
                        )

                        if student_program is not None:
                            structure_id = cast(int, student_program.structure_id)
                            structure_semester_id = cast(
                                int, student_semester.structure_semester_id
                            )
                            module_credits: float | None = None
                            if data.get("credits") is not None:
                                try:
                                    module_credits = float(data["credits"])
                                except (TypeError, ValueError):
                                    module_credits = None

                            semester_module_id = (
                                self._lookup_semester_module_for_student_semester(
                                    session,
                                    module_code=str(data["module_code"]),
                                    structure_semester_id=structure_semester_id,
                                    module_type=data.get("type"),
                                    credits=module_credits,
                                )
                            )

                            if not semester_module_id and structure_semester_id:
                                semester_module_id = (
                                    self._create_missing_semester_module(
                                        session,
                                        data["module_code"],
                                        data.get("module_name", data["module_code"]),
                                        data.get("type", "Core"),
                                        float(data.get("credits", 0)),
                                        structure_semester_id,
                                    )
                                )

                            if (
                                not semester_module_id
                                and not structure_semester_id
                                and structure_id
                            ):
                                semester_module_id = self.get_semester_module_by_code(
                                    data["module_code"], structure_id
                                )

                if not existing and semester_module_id:
                    existing = (
                        session.query(StudentModule)
                        .filter(
                            StudentModule.student_semester_id == student_semester_db_id
                        )
                        .filter(StudentModule.semester_module_id == semester_module_id)
                        .filter(StudentModule.cms_id.is_(None))
                        .first()
                    )

                if not semester_module_id and student_semester_db_id:
                    logger.error(
                        f"Missing semester module - "
                        f"std_module_id={std_module_id}, "
                        f"student_semester_id={student_semester_db_id}, "
                        f"module_code={data.get('module_code')}, "
                        f"module_name={data.get('module_name')}"
                    )
                    return False, "Semester module not found in database"

                if not semester_module_id:
                    logger.error(
                        f"Cannot resolve semester_module_id - "
                        f"std_module_id={std_module_id}, "
                        f"student_semester_id={student_semester_db_id}, "
                        f"module_code={data.get('module_code')}, data={data}"
                    )
                    return False, "Cannot resolve semester_module_id"

                if existing:
                    existing.cms_id = std_module_id  # type: ignore
                    existing.semester_module_id = semester_module_id  # type: ignore
                    if "status" in data:
                        existing.status = normalize_student_module_status(
                            data["status"]  # type: ignore
                        )
                    if "credits" in data:
                        existing.credits = float(data["credits"])  # type: ignore
                    if "marks" in data:
                        existing.marks = data["marks"]
                    if "grade" in data:
                        existing.grade = data["grade"]
                    if "student_semester_id" in data:
                        existing.student_semester_id = data["student_semester_id"]
                    if "student_semester_db_id" in data:
                        existing.student_semester_id = data["student_semester_db_id"]

                    session.commit()
                    logger.info(f"Updated student module {std_module_id}")
                    return True, "Student module updated"
                else:
                    new_module = StudentModule(
                        cms_id=std_module_id,
                        semester_module_id=semester_module_id,
                        status=normalize_student_module_status(data.get("status")),
                        credits=float(data.get("credits", 0)),
                        marks=data.get("marks", "NM"),
                        grade=data.get("grade", "NM"),
                        student_semester_id=student_semester_db_id,
                    )
                    session.add(new_module)
                    session.commit()
                    logger.info(f"Created student module {std_module_id}")
                    return True, "Student module created"

            except Exception as e:
                session.rollback()
                error_msg = f"Error upserting student module: {str(e)}"
                logger.error(
                    f"Error upserting student module - std_module_id={std_module_id}, "
                    f"student_semester_id={student_semester_db_id}, "
                    f"semester_module_id={semester_module_id}, "
                    f"module_code={data.get('module_code')}, "
                    f"error={str(e)}, data={data}",
                )
                return False, error_msg

    def upsert_next_of_kin(
        self, student_number: str, next_of_kin_list: list[dict]
    ) -> tuple[bool, str]:
        try:
            numeric_student_number = int(student_number)
        except (TypeError, ValueError):
            return False, "Invalid student number"

        with self._session() as session:
            try:
                existing_kin = (
                    session.query(NextOfKin)
                    .filter(NextOfKin.std_no == numeric_student_number)
                    .all()
                )

                existing_map = {
                    (kin.relationship, kin.name): kin for kin in existing_kin
                }

                for kin_data in next_of_kin_list:
                    name = kin_data.get("name")
                    relationship = kin_data.get("relationship")

                    if not name or not relationship:
                        continue

                    key = (relationship, name)

                    if key in existing_map:
                        existing = existing_map[key]
                        if kin_data.get("phone"):
                            existing.phone = kin_data["phone"]
                        if kin_data.get("email"):
                            existing.email = kin_data["email"]
                        if kin_data.get("occupation"):
                            existing.occupation = kin_data["occupation"]
                        if kin_data.get("address"):
                            existing.address = kin_data["address"]
                        if kin_data.get("country"):
                            existing.country = kin_data["country"]
                    else:
                        new_kin = NextOfKin(
                            std_no=numeric_student_number,
                            name=name,
                            relationship=relationship,
                            phone=kin_data.get("phone"),
                            email=kin_data.get("email"),
                            occupation=kin_data.get("occupation"),
                            address=kin_data.get("address"),
                            country=kin_data.get("country"),
                        )
                        session.add(new_kin)

                session.commit()
                logger.info(f"Updated next of kin records for student {student_number}")
                return True, "Next of kin records updated"

            except Exception as e:
                session.rollback()
                error_msg = f"Error upserting next of kin: {str(e)}"
                logger.error(
                    f"Error upserting next of kin - student_number={student_number}, "
                    f"num_records={len(next_of_kin_list)}, "
                    f"error={str(e)}, data={next_of_kin_list}",
                )
                return False, error_msg

    def upsert_student_education(self, data: dict) -> tuple[bool, str]:
        education_id: int = 0
        std_no: Optional[int] = None
        with self._session() as session:
            try:
                education_id = int(data["cms_id"])
                std_no = _coerce_int(data.get("std_no"))

                if not std_no:
                    return False, "Missing student number"

                existing = (
                    session.query(StudentEducation)
                    .filter(StudentEducation.cms_id == education_id)
                    .first()
                )

                if existing:
                    existing.cms_id = education_id  # type: ignore
                    if "school_name" in data:
                        existing.school_name = data["school_name"]
                    if "type" in data:
                        existing.type = data["type"]
                    if "level" in data:
                        existing.level = data["level"]
                    if "start_date" in data:
                        existing.start_date = _coerce_datetime(data["start_date"])
                    if "end_date" in data:
                        existing.end_date = _coerce_datetime(data["end_date"])

                    session.commit()
                    logger.info(f"Updated student education {education_id}")
                    return True, "Student education updated"
                else:
                    new_education = StudentEducation(
                        cms_id=education_id,
                        std_no=std_no,
                        school_name=data.get("school_name", ""),
                        type=data.get("type"),
                        level=data.get("level"),
                        start_date=_coerce_datetime(data.get("start_date")),
                        end_date=_coerce_datetime(data.get("end_date")),
                    )
                    session.add(new_education)
                    session.commit()
                    logger.info(f"Created student education {education_id}")
                    return True, "Student education created"

            except Exception as e:
                session.rollback()
                error_msg = f"Error upserting student education: {str(e)}"
                logger.error(
                    f"Error upserting student education - education_id={education_id}, "
                    f"std_no={std_no}, school_name={data.get('school_name')}, "
                    f"error={str(e)}, data={data}",
                )
                return False, error_msg

    def lookup_structure_semester_id(
        self, structure_id: int, semester_number: str
    ) -> Optional[int]:
        cache_key = (structure_id, semester_number)

        if cache_key in _structure_semester_cache:
            logger.debug(
                f"Cache hit for structure {structure_id}, semester {semester_number}"
            )
            return _structure_semester_cache[cache_key]

        logger.debug(
            f"Cache miss for structure {structure_id}, semester {semester_number} - querying database"
        )

        with self._session() as session:
            result = (
                session.query(StructureSemester.id)
                .filter(StructureSemester.structure_id == structure_id)
                .filter(StructureSemester.semester_number == semester_number)
                .first()
            )
            structure_semester_id = result[0] if result else None

            _structure_semester_cache[cache_key] = structure_semester_id

            return structure_semester_id

    def ensure_structure_semester(
        self,
        structure_id: int,
        semester_number: str,
        name: str,
        *,
        total_credits: float = 0.0,
    ) -> Optional[int]:
        normalized_semester_number = semester_number.strip()
        if not normalized_semester_number:
            return None

        normalized_name = name.strip() or f"Semester {normalized_semester_number}"
        cache_key = (structure_id, normalized_semester_number)

        with self._session() as session:
            structure_semester = (
                session.query(StructureSemester)
                .filter(StructureSemester.structure_id == structure_id)
                .filter(
                    StructureSemester.semester_number == normalized_semester_number
                )
                .first()
            )

            if structure_semester:
                if normalized_name and structure_semester.name != normalized_name:
                    structure_semester.name = normalized_name  # type: ignore
                if (
                    float(structure_semester.total_credits or 0.0) == 0.0
                    and float(total_credits) != 0.0
                ):
                    structure_semester.total_credits = total_credits  # type: ignore
                session.commit()
                session.refresh(structure_semester)
                structure_semester_id = cast(int, structure_semester.id)
                _structure_semester_cache[cache_key] = structure_semester_id
                return structure_semester_id

            structure_semester = StructureSemester(
                structure_id=structure_id,
                semester_number=normalized_semester_number,
                name=normalized_name,
                total_credits=float(total_credits),
            )
            session.add(structure_semester)
            session.commit()
            session.refresh(structure_semester)

            structure_semester_id = cast(int, structure_semester.id)
            _structure_semester_cache[cache_key] = structure_semester_id
            logger.warning(
                f"Created missing structure semester - structure_id={structure_id}, "
                f"semester_number={normalized_semester_number}, "
                f"structure_semester_id={structure_semester_id}, "
                f"name={normalized_name}"
            )
            return structure_semester_id

    def lookup_sponsor_by_code(self, sponsor_code: str) -> Optional[int]:
        normalized_sponsor_code = _normalize_sponsor_key(sponsor_code)
        if normalized_sponsor_code is None:
            return None

        if normalized_sponsor_code in _sponsor_code_cache:
            logger.debug(f"Cache hit for sponsor code '{normalized_sponsor_code}'")
            return _sponsor_code_cache[normalized_sponsor_code]

        logger.debug(
            f"Cache miss for sponsor code '{normalized_sponsor_code}' - querying database"
        )

        with self._session() as session:
            result = (
                session.query(Sponsor.id, Sponsor.name)
                .filter(Sponsor.code == normalized_sponsor_code)
                .first()
            )
            sponsor_id = result[0] if result else None
            sponsor_name = result[1] if result else None

            _cache_sponsor(
                sponsor_id,
                sponsor_code=normalized_sponsor_code,
                sponsor_name=sponsor_name,
            )

            return sponsor_id

    def lookup_sponsor_by_name(self, sponsor_name: str) -> Optional[int]:
        normalized_sponsor_name = _normalize_sponsor_key(sponsor_name)
        if normalized_sponsor_name is None:
            return None

        if normalized_sponsor_name in _sponsor_name_cache:
            logger.debug(f"Cache hit for sponsor name '{normalized_sponsor_name}'")
            return _sponsor_name_cache[normalized_sponsor_name]

        logger.debug(
            f"Cache miss for sponsor name '{normalized_sponsor_name}' - querying database"
        )

        with self._session() as session:
            result = (
                session.query(Sponsor.id, Sponsor.code)
                .filter(Sponsor.name == normalized_sponsor_name)
                .first()
            )
            sponsor_id = result[0] if result else None
            sponsor_code = result[1] if result else None

            _cache_sponsor(
                sponsor_id,
                sponsor_code=sponsor_code,
                sponsor_name=normalized_sponsor_name,
            )

            return sponsor_id

    def lookup_sponsor(self, sponsor_value: str) -> Optional[int]:
        normalized_value = _normalize_sponsor_key(sponsor_value)
        if normalized_value is None:
            return None

        sponsor_id = self.lookup_sponsor_by_code(normalized_value)
        if sponsor_id:
            return sponsor_id

        return self.lookup_sponsor_by_name(normalized_value)

    def create_sponsor(
        self, sponsor_code: str, sponsor_name: Optional[str] = None
    ) -> Optional[int]:
        normalized_sponsor_code = _normalize_sponsor_key(sponsor_code)
        if normalized_sponsor_code is None:
            return None

        existing_sponsor_id = self.lookup_sponsor(normalized_sponsor_code)
        if existing_sponsor_id:
            return existing_sponsor_id

        base_code = normalized_sponsor_code[:10]

        with self._session() as session:
            base_name = (
                sponsor_name.strip()
                if sponsor_name and sponsor_name.strip()
                else normalized_sponsor_code
            )
            candidate_name = base_name
            candidate_code = base_code
            suffix = 1

            while (
                session.query(Sponsor.id).filter(Sponsor.name == candidate_name).first()
            ):
                candidate_name = f"{base_name} {suffix}"
                suffix += 1

            code_suffix = 1
            while (
                session.query(Sponsor.id).filter(Sponsor.code == candidate_code).first()
            ):
                suffix_str = str(code_suffix)
                prefix_length = max(1, 10 - len(suffix_str))
                candidate_code = f"{base_code[:prefix_length]}{suffix_str}"
                code_suffix += 1

            sponsor = Sponsor(
                name=candidate_name,
                code=candidate_code,
                updated_at=datetime.datetime.utcnow(),
            )
            session.add(sponsor)

            try:
                session.commit()
                session.refresh(sponsor)
                _cache_sponsor(
                    sponsor.id,
                    sponsor_code=sponsor.code,
                    sponsor_name=sponsor.name,
                )
                logger.warning(
                    f"Created missing sponsor - sponsor_id={sponsor.id}, "
                    f"sponsor_code={candidate_code}, sponsor_name={candidate_name}"
                )
                return sponsor.id
            except IntegrityError:
                session.rollback()
                result = (
                    session.query(Sponsor.id, Sponsor.code, Sponsor.name)
                    .filter(
                        or_(
                            Sponsor.code == candidate_code,
                            Sponsor.name == base_name,
                        )
                    )
                    .first()
                )
                if result:
                    sponsor_id, existing_code, existing_name = result
                    _cache_sponsor(
                        sponsor_id,
                        sponsor_code=existing_code,
                        sponsor_name=existing_name,
                    )
                    return sponsor_id
                logger.error(
                    f"Failed to create sponsor due to integrity error - sponsor_code={candidate_code}"
                )
                return None
            except Exception as e:
                session.rollback()
                logger.error(
                    f"Failed to create sponsor - sponsor_code={candidate_code}, error={str(e)}"
                )
                return None

    def preload_structure_semesters(self, structure_id: int) -> int:
        logger.info(f"Preloading structure semesters for structure {structure_id}")

        with self._session() as session:
            results = (
                session.query(StructureSemester.id, StructureSemester.semester_number)
                .filter(StructureSemester.structure_id == structure_id)
                .all()
            )

            for structure_semester_id, semester_number in results:
                cache_key = (structure_id, semester_number)
                _structure_semester_cache[cache_key] = structure_semester_id

            logger.info(
                f"Preloaded {len(results)} semesters for structure {structure_id}"
            )
            return len(results)

    def preload_all_sponsors(self) -> int:
        logger.info("Preloading all sponsors")

        with self._session() as session:
            results = session.query(Sponsor.id, Sponsor.code, Sponsor.name).all()

            for sponsor_id, sponsor_code, sponsor_name in results:
                _cache_sponsor(
                    sponsor_id,
                    sponsor_code=sponsor_code,
                    sponsor_name=sponsor_name,
                )

            logger.info(f"Preloaded {len(results)} sponsors")
            return len(results)

    def clear_structure_semester_cache(self) -> None:
        global _structure_semester_cache
        _structure_semester_cache.clear()
        logger.info("Cleared structure semester cache")

    def clear_sponsor_cache(self) -> None:
        global _sponsor_code_cache, _sponsor_name_cache
        _sponsor_code_cache.clear()
        _sponsor_name_cache.clear()
        logger.info("Cleared sponsor cache")

    def get_active_term_code(self) -> Optional[str]:
        with self._session() as session:
            result = session.query(Term.code).filter(Term.is_active == True).first()
            return result[0] if result else None

    def get_active_term_semesters_for_student(
        self, std_no: str, active_term_code: str
    ) -> list[dict]:
        try:
            numeric_std_no = int(std_no)
        except (TypeError, ValueError):
            return []

        preserved_semesters: list[dict] = []
        with self._session() as session:
            try:
                semesters = (
                    session.query(
                        StudentSemester.id,
                        StudentSemester.cms_id,
                        StudentSemester.term_code,
                        StudentSemester.structure_semester_id,
                        StudentSemester.status,
                        StudentSemester.caf_date,
                        StudentSemester.sponsor_id,
                        StudentProgram.id.label("student_program_id"),
                        StudentProgram.structure_id,
                    )
                    .join(
                        StudentProgram,
                        StudentSemester.student_program_id == StudentProgram.id,
                    )
                    .filter(StudentProgram.std_no == numeric_std_no)
                    .filter(StudentSemester.term_code == active_term_code)
                    .all()
                )

                for sem in semesters:
                    modules = (
                        session.query(
                            StudentModule.id,
                            StudentModule.cms_id,
                            StudentModule.semester_module_id,
                            StudentModule.status,
                            StudentModule.credits,
                            StudentModule.marks,
                            StudentModule.grade,
                        )
                        .filter(StudentModule.student_semester_id == sem.id)
                        .all()
                    )

                    preserved_semesters.append(
                        {
                            "id": sem.id,
                            "cms_id": sem.cms_id,
                            "term": sem.term_code,
                            "structure_semester_id": sem.structure_semester_id,
                            "status": sem.status,
                            "caf_date": sem.caf_date,
                            "sponsor_id": sem.sponsor_id,
                            "student_program_id": sem.student_program_id,
                            "structure_id": sem.structure_id,
                            "modules": [
                                {
                                    "id": mod.id,
                                    "cms_id": mod.cms_id,
                                    "semester_module_id": mod.semester_module_id,
                                    "status": mod.status,
                                    "credits": mod.credits,
                                    "marks": mod.marks,
                                    "grade": mod.grade,
                                }
                                for mod in modules
                            ],
                        }
                    )

                logger.info(
                    f"Preserved {len(preserved_semesters)} active term semesters for student {std_no}"
                )
                return preserved_semesters
            except Exception as e:
                logger.error(
                    f"Error getting active term semesters for student {std_no}: {str(e)}"
                )
                return []

    def restore_preserved_semester(
        self, std_program_id: int, semester_data: dict
    ) -> tuple[bool, str, Optional[int]]:
        with self._session() as session:
            try:
                semester_id = semester_data.get("id")
                if not semester_id:
                    return False, "No semester ID provided", None

                existing = (
                    session.query(StudentSemester)
                    .filter(StudentSemester.id == semester_id)
                    .first()
                )

                if existing:
                    logger.info(
                        f"Semester {semester_id} already exists for program {std_program_id}, skipping restore"
                    )
                    return True, "Semester already exists", semester_id

                new_semester = StudentSemester(
                    id=semester_id,
                    cms_id=semester_data.get("cms_id"),
                    student_program_id=std_program_id,
                    term_code=semester_data.get("term"),
                    structure_semester_id=semester_data["structure_semester_id"],
                    status=semester_data.get("status", "Active"),
                    caf_date=semester_data.get("caf_date"),
                    sponsor_id=semester_data.get("sponsor_id"),
                )
                session.add(new_semester)
                session.flush()

                for module_data in semester_data.get("modules", []):
                    existing_module = (
                        session.query(StudentModule)
                        .filter(StudentModule.id == module_data.get("id"))
                        .first()
                    )
                    if existing_module:
                        continue

                    new_module = StudentModule(
                        id=module_data.get("id"),
                        cms_id=module_data.get("cms_id"),
                        semester_module_id=module_data["semester_module_id"],
                        status=module_data.get("status", "Registered"),
                        credits=module_data.get("credits", 0),
                        marks=module_data.get("marks", ""),
                        grade=module_data.get("grade", ""),
                        student_semester_id=semester_id,
                    )
                    session.add(new_module)

                session.commit()
                logger.info(
                    f"Restored semester {semester_id} with {len(semester_data.get('modules', []))} modules "
                    f"for program {std_program_id}"
                )
                return True, "Semester restored", semester_id
            except Exception as e:
                session.rollback()
                logger.error(
                    f"Error restoring semester for program {std_program_id}: {str(e)}"
                )
                return False, str(e), None

    def delete_student_programs(self, std_no: str) -> tuple[bool, int]:
        try:
            numeric_std_no = int(std_no)
        except (TypeError, ValueError):
            return False, 0

        with self._session() as session:
            try:
                deleted_count = (
                    session.query(StudentProgram)
                    .filter(StudentProgram.std_no == numeric_std_no)
                    .delete(synchronize_session="fetch")
                )
                session.commit()
                logger.info(
                    f"Deleted {deleted_count} student programs for student {std_no}"
                )
                return True, deleted_count
            except Exception as e:
                session.rollback()
                logger.error(
                    f"Error deleting student programs for student {std_no}: {str(e)}"
                )
                return False, 0
