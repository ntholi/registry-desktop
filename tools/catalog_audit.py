from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.orm import Session

import database.connection as db_connection
from base.browser import BASE_URL, Browser
from database import (
    Module,
    Program,
    School,
    SemesterModule,
    Structure,
    StructureSemester,
)
from database.bootstrap import ensure_database_schema
from features.sync.modules.scraper import (
    _extract_pager_bounds as extract_module_pager_bounds,
)
from features.sync.structures.scraper import (
    _extract_pager_bounds as extract_structure_pager_bounds,
)
from utils.normalizers import normalize_module_type


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_float(value: Any) -> float:
    return round(float(value or 0.0), 4)


def require_int(value: int | None) -> int:
    if value is None:
        raise ValueError("Expected integer value")
    return int(value)


def fetch_page(browser: Browser, url: str) -> BeautifulSoup:
    response = browser.fetch(url)
    return BeautifulSoup(response.text, "lxml")


def pager_total(page: BeautifulSoup, extractor) -> int:
    bounds = extractor(page)
    if not bounds:
        return 0
    return int(bounds[2])


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


@dataclass
class AuditRecorder:
    schools: set[tuple[int, str, str]] = field(default_factory=set)
    programs: set[tuple[int, int, str, str, str]] = field(default_factory=set)
    structures: set[tuple[int, int, str, str]] = field(default_factory=set)
    semesters: set[tuple[int, int, str, str, float]] = field(default_factory=set)
    semester_modules: set[tuple[int, int, str, str, str, float, bool]] = field(
        default_factory=set
    )
    modules: set[tuple[int, str, str, str, str]] = field(default_factory=set)
    pager_mismatches: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {
            "schools": [],
            "programs": [],
            "structures": [],
            "semesters": [],
            "semester_modules": [],
            "modules": [],
        }
    )
    school_codes: dict[int, str] = field(default_factory=dict)

    def record_schools(
        self, schools: Sequence[Mapping[str, Any]], expected: int
    ) -> None:
        for school in schools:
            school_id = int(school["cms_id"])
            school_code = normalize_text(school["code"])
            school_name = normalize_text(school["name"])
            self.school_codes[school_id] = school_code
            self.schools.add((school_id, school_code, school_name))

        if expected and expected != len(schools):
            self.pager_mismatches["schools"].append(
                {"expected": expected, "actual": len(schools)}
            )

    def record_programs(
        self,
        school_id: int,
        programs: Sequence[Mapping[str, Any]],
        expected: int,
    ) -> None:
        school_code = self.school_codes.get(school_id, str(school_id))
        print(
            json.dumps(
                {
                    "stage": "school",
                    "school_id": school_id,
                    "school": school_code,
                    "programs": len(programs),
                }
            ),
            flush=True,
        )

        for program in programs:
            self.programs.add(
                (
                    int(program["cms_id"]),
                    school_id,
                    normalize_text(program["code"]),
                    normalize_text(program["name"]),
                    normalize_text(program.get("level")),
                )
            )

        if expected and expected != len(programs):
            self.pager_mismatches["programs"].append(
                {
                    "school_id": school_id,
                    "school": school_code,
                    "expected": expected,
                    "actual": len(programs),
                }
            )

    def record_structures(
        self,
        program_id: int,
        structures: Sequence[Mapping[str, Any]],
        expected: int,
    ) -> None:
        for structure in structures:
            self.structures.add(
                (
                    int(structure["cms_id"]),
                    program_id,
                    normalize_text(structure["code"]),
                    normalize_text(structure.get("desc")),
                )
            )

        if expected and expected != len(structures):
            self.pager_mismatches["structures"].append(
                {
                    "program_id": program_id,
                    "expected": expected,
                    "actual": len(structures),
                }
            )

    def record_semesters(
        self,
        structure_id: int,
        semesters: Sequence[Mapping[str, Any]],
        expected: int,
    ) -> None:
        for semester in semesters:
            self.semesters.add(
                (
                    int(semester["cms_id"]),
                    structure_id,
                    normalize_text(semester["semester_number"]),
                    normalize_text(semester["name"]),
                    normalize_float(semester["total_credits"]),
                )
            )

        if expected and expected != len(semesters):
            self.pager_mismatches["semesters"].append(
                {
                    "structure_id": structure_id,
                    "expected": expected,
                    "actual": len(semesters),
                }
            )

    def record_semester_modules(
        self,
        semester_id: int,
        semester_modules: Sequence[Mapping[str, Any]],
        expected: int,
    ) -> None:
        for semester_module in semester_modules:
            self.semester_modules.add(
                (
                    int(semester_module["cms_id"]),
                    semester_id,
                    normalize_text(semester_module["module_code"]),
                    normalize_text(semester_module["module_name"]),
                    normalize_module_type(str(semester_module["type"])),
                    normalize_float(semester_module["credits"]),
                    bool(semester_module["hidden"]),
                )
            )

        if expected and expected != len(semester_modules):
            self.pager_mismatches["semester_modules"].append(
                {
                    "semester_id": semester_id,
                    "expected": expected,
                    "actual": len(semester_modules),
                }
            )

    def record_modules(
        self, modules: Sequence[Mapping[str, Any]], expected: int
    ) -> None:
        self.modules = {
            (
                int(module["cms_id"]),
                normalize_text(module["code"]),
                normalize_text(module["name"]),
                normalize_text(module["status"]),
                normalize_text(module["timestamp"]),
            )
            for module in modules
        }

        if expected and expected != len(modules):
            self.pager_mismatches["modules"].append(
                {"expected": expected, "actual": len(modules)}
            )


def admin_engine(source_url: URL) -> Engine:
    return create_engine(source_url.set(database="postgres"), pool_pre_ping=True)


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def create_audit_database(source_url: URL) -> tuple[str, URL, str]:
    database_name = f"registry_catalog_audit_{uuid.uuid4().hex[:8]}"
    audit_url = source_url.set(database=database_name)
    bootstrap_mode = "template"

    source_database = quote_identifier(source_url.database or "postgres")
    target_database = quote_identifier(database_name)

    with (
        admin_engine(source_url)
        .connect()
        .execution_options(isolation_level="AUTOCOMMIT") as conn
    ):
        try:
            conn.execute(
                text(f"CREATE DATABASE {target_database} TEMPLATE {source_database}")
            )
        except Exception:
            bootstrap_mode = "create_all"
            conn.execute(text(f"CREATE DATABASE {target_database}"))

    if bootstrap_mode == "create_all":
        bootstrap_engine = create_engine(audit_url, pool_pre_ping=True)
        ensure_database_schema(bootstrap_engine)
        bootstrap_engine.dispose()

    return database_name, audit_url, bootstrap_mode


def reset_catalog_tables(audit_url: URL) -> None:
    engine = create_engine(audit_url, pool_pre_ping=True)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE semester_modules, structure_semesters, structures, programs, schools, modules RESTART IDENTITY CASCADE"
            )
        )
    engine.dispose()


def patch_database_url(audit_url: URL) -> None:
    db_connection.DATABASE_ENV = "local"
    db_connection.DESKTOP_ENV = "dev"
    db_connection.DATABASE_LOCAL_URL = audit_url.render_as_string(hide_password=False)


def install_audit_wrappers(recorder: AuditRecorder) -> None:
    import features.sync.modules.scraper as module_scraper_module
    import features.sync.modules.service as module_service_module
    import features.sync.structures.scraper as structure_scraper_module
    import features.sync.structures.service as structure_service_module

    browser = Browser()

    original_scrape_all_schools = structure_scraper_module.scrape_all_schools
    original_scrape_programs = structure_scraper_module.scrape_programs
    original_scrape_structures = structure_scraper_module.scrape_structures
    original_scrape_semesters = structure_scraper_module.scrape_semesters
    original_scrape_semester_modules = structure_scraper_module.scrape_semester_modules
    original_scrape_all_modules = module_scraper_module.scrape_all_modules

    def audited_scrape_all_schools():
        schools = original_scrape_all_schools()
        page = fetch_page(browser, f"{BASE_URL}/f_schoollist.php?cmd=resetall")
        recorder.record_schools(
            schools, pager_total(page, extract_structure_pager_bounds)
        )
        return schools

    def audited_scrape_programs(school_id: int):
        programs = original_scrape_programs(school_id)
        page = fetch_page(
            browser,
            f"{BASE_URL}/f_programlist.php?showmaster=1&SchoolID={school_id}",
        )
        recorder.record_programs(
            school_id,
            programs,
            pager_total(page, extract_structure_pager_bounds),
        )
        return programs

    def audited_scrape_structures(program_id: int):
        structures = original_scrape_structures(program_id)
        page = fetch_page(
            browser,
            f"{BASE_URL}/f_structurelist.php?showmaster=1&ProgramID={program_id}",
        )
        recorder.record_structures(
            program_id,
            structures,
            pager_total(page, extract_structure_pager_bounds),
        )
        return structures

    def audited_scrape_semesters(structure_id: int):
        semesters = original_scrape_semesters(structure_id)
        page = fetch_page(
            browser,
            f"{BASE_URL}/f_semesterlist.php?showmaster=1&StructureID={structure_id}",
        )
        recorder.record_semesters(
            structure_id,
            semesters,
            pager_total(page, extract_structure_pager_bounds),
        )
        return semesters

    def audited_scrape_semester_modules(semester_id: int):
        semester_modules = original_scrape_semester_modules(semester_id)
        page = fetch_page(
            browser,
            f"{BASE_URL}/f_semmodulelist.php?showmaster=1&SemesterID={semester_id}",
        )
        recorder.record_semester_modules(
            semester_id,
            semester_modules,
            pager_total(page, extract_structure_pager_bounds),
        )
        return semester_modules

    def audited_scrape_all_modules(progress_callback=None):
        modules = original_scrape_all_modules(progress_callback=progress_callback)
        page = fetch_page(browser, f"{BASE_URL}/f_modulelist.php?cmd=resetall")
        recorder.record_modules(modules, pager_total(page, extract_module_pager_bounds))
        return modules

    structure_service_module.scrape_all_schools = audited_scrape_all_schools
    structure_service_module.scrape_programs = audited_scrape_programs
    structure_service_module.scrape_structures = audited_scrape_structures
    structure_service_module.scrape_semesters = audited_scrape_semesters
    structure_service_module.scrape_semester_modules = audited_scrape_semester_modules
    module_service_module.scrape_all_modules = audited_scrape_all_modules


def run_import(audit_url: URL) -> AuditRecorder:
    patch_database_url(audit_url)
    recorder = AuditRecorder()
    install_audit_wrappers(recorder)

    from features.sync.modules.repository import ModuleRepository
    from features.sync.modules.service import ModuleSyncService
    from features.sync.structures.repository import StructureRepository
    from features.sync.structures.service import SchoolSyncService

    module_repository = ModuleRepository()
    structure_repository = StructureRepository()
    module_service = ModuleSyncService(module_repository)
    school_service = SchoolSyncService(structure_repository)

    def quiet_progress(*args):
        return None

    print(json.dumps({"stage": "import_modules_start"}), flush=True)
    module_service.fetch_and_save_all_modules(quiet_progress)
    print(
        json.dumps({"stage": "import_modules_done", "modules": len(recorder.modules)}),
        flush=True,
    )
    print(json.dumps({"stage": "import_structures_start"}), flush=True)
    school_service.import_all_schools_structures(quiet_progress, fetch_semesters=True)
    print(
        json.dumps(
            {
                "stage": "import_structures_done",
                "schools": len(recorder.schools),
                "programs": len(recorder.programs),
                "structures": len(recorder.structures),
                "semesters": len(recorder.semesters),
                "semester_modules": len(recorder.semester_modules),
            }
        ),
        flush=True,
    )

    module_repository._engine.dispose()
    structure_repository._engine.dispose()
    return recorder


def collect_db_catalog(
    audit_url: URL,
) -> tuple[dict[str, Any], dict[str, int]]:
    engine = create_engine(audit_url, pool_pre_ping=True)
    with Session(engine) as session:
        schools = {
            (
                require_int(school.cms_id),
                normalize_text(school.code),
                normalize_text(school.name),
            )
            for school in session.query(School).filter(School.cms_id.isnot(None)).all()
        }
        programs = {
            (
                require_int(program.cms_id),
                require_int(school.cms_id),
                normalize_text(program.code),
                normalize_text(program.name),
                normalize_text(program.level),
            )
            for program, school in session.query(Program, School)
            .join(School, Program.school_id == School.id)
            .filter(Program.cms_id.isnot(None))
            .filter(School.cms_id.isnot(None))
            .all()
        }
        structures = {
            (
                require_int(structure.cms_id),
                require_int(program.cms_id),
                normalize_text(structure.code),
                normalize_text(structure.desc),
            )
            for structure, program in session.query(Structure, Program)
            .join(Program, Structure.program_id == Program.id)
            .filter(Structure.cms_id.isnot(None))
            .filter(Program.cms_id.isnot(None))
            .all()
        }
        semesters = {
            (
                require_int(semester.cms_id),
                require_int(structure.cms_id),
                normalize_text(semester.semester_number),
                normalize_text(semester.name),
                normalize_float(semester.total_credits),
            )
            for semester, structure in session.query(StructureSemester, Structure)
            .join(Structure, StructureSemester.structure_id == Structure.id)
            .filter(StructureSemester.cms_id.isnot(None))
            .filter(Structure.cms_id.isnot(None))
            .all()
        }
        semester_modules = {
            (
                require_int(semester_module.cms_id),
                require_int(semester.cms_id),
                normalize_text(module.code),
                normalize_text(module.name),
                normalize_module_type(str(semester_module.type)),
                normalize_float(semester_module.credits),
                bool(semester_module.hidden),
            )
            for semester_module, semester, module in session.query(
                SemesterModule,
                StructureSemester,
                Module,
            )
            .join(StructureSemester, SemesterModule.semester_id == StructureSemester.id)
            .join(Module, SemesterModule.module_id == Module.id)
            .filter(SemesterModule.cms_id.isnot(None))
            .filter(StructureSemester.cms_id.isnot(None))
            .all()
        }
        modules = {
            (
                require_int(module.cms_id),
                normalize_text(module.code),
                normalize_text(module.name),
                normalize_text(module.status),
                normalize_text(module.timestamp),
            )
            for module in session.query(Module).filter(Module.cms_id.isnot(None)).all()
        }
        module_placeholders = {
            normalize_text(module.code)
            for module in session.query(Module).filter(Module.cms_id.is_(None)).all()
        }
        metadata = {
            "schools_total_rows": session.query(School).count(),
            "programs_total_rows": session.query(Program).count(),
            "structures_total_rows": session.query(Structure).count(),
            "semesters_total_rows": session.query(StructureSemester).count(),
            "semester_modules_total_rows": session.query(SemesterModule).count(),
            "modules_total_rows": session.query(Module).count(),
            "modules_without_cms_id": session.query(Module)
            .filter(Module.cms_id.is_(None))
            .count(),
        }

    engine.dispose()
    return {
        "schools": schools,
        "programs": programs,
        "structures": structures,
        "semesters": semesters,
        "semester_modules": semester_modules,
        "modules": modules,
        "module_placeholders": module_placeholders,
    }, metadata


def drop_audit_database(source_url: URL, database_name: str) -> None:
    target_database = quote_identifier(database_name)
    with (
        admin_engine(source_url)
        .connect()
        .execution_options(isolation_level="AUTOCOMMIT") as conn
    ):
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :database_name AND pid <> pg_backend_pid()"
            ),
            {"database_name": database_name},
        )
        conn.execute(text(f"DROP DATABASE IF EXISTS {target_database}"))


def selected_database_url() -> URL:
    selected = (
        db_connection.DATABASE_REMOTE_URL
        if db_connection.is_remote_database()
        else db_connection.DATABASE_LOCAL_URL
    )
    if not selected:
        raise ValueError("No database URL is configured")
    return make_url(selected)


def main() -> None:
    logging.disable(logging.CRITICAL)

    source_url = selected_database_url()
    database_name, audit_url, bootstrap_mode = create_audit_database(source_url)
    recorder: AuditRecorder | None = None

    try:
        reset_catalog_tables(audit_url)
        recorder = run_import(audit_url)
        db_catalog, db_metadata = collect_db_catalog(audit_url)
    finally:
        drop_audit_database(source_url, database_name)

    if recorder is None:
        raise ValueError("Audit recorder was not created")

    comparison = {
        "schools": diff_summary(recorder.schools, db_catalog["schools"]),
        "programs": diff_summary(recorder.programs, db_catalog["programs"]),
        "structures": diff_summary(recorder.structures, db_catalog["structures"]),
        "semesters": diff_summary(recorder.semesters, db_catalog["semesters"]),
        "semester_modules": diff_summary(
            recorder.semester_modules,
            db_catalog["semester_modules"],
        ),
        "modules": diff_summary(recorder.modules, db_catalog["modules"]),
    }

    live_module_codes = {module_code for _, module_code, _, _, _ in recorder.modules}
    expected_placeholder_codes = {
        module_code
        for _, _, module_code, _, _, _, _ in recorder.semester_modules
        if module_code not in live_module_codes
    }
    placeholder_comparison = {
        "expected_count": len(expected_placeholder_codes),
        "actual_count": len(db_catalog["module_placeholders"]),
        "missing_count": len(expected_placeholder_codes - db_catalog["module_placeholders"]),
        "extra_count": len(db_catalog["module_placeholders"] - expected_placeholder_codes),
        "missing_samples": sorted(
            expected_placeholder_codes - db_catalog["module_placeholders"]
        )[:10],
        "extra_samples": sorted(
            db_catalog["module_placeholders"] - expected_placeholder_codes
        )[:10],
    }

    status = "pass"
    if any(recorder.pager_mismatches[key] for key in recorder.pager_mismatches):
        status = "fail"
    if any(
        section["missing_count"] or section["extra_count"]
        for section in comparison.values()
    ):
        status = "fail"
    if (
        placeholder_comparison["missing_count"]
        or placeholder_comparison["extra_count"]
    ):
        status = "fail"

    summary = {
        "status": status,
        "database": {
            "source_database": source_url.database,
            "bootstrap_mode": bootstrap_mode,
        },
        "live_counts": {
            "schools": len(recorder.schools),
            "programs": len(recorder.programs),
            "structures": len(recorder.structures),
            "semesters": len(recorder.semesters),
            "semester_modules": len(recorder.semester_modules),
            "modules": len(recorder.modules),
        },
        "pager_mismatches": {
            key: {"count": len(value), "samples": value[:5]}
            for key, value in recorder.pager_mismatches.items()
        },
        "module_placeholders": placeholder_comparison,
        "db_metadata": db_metadata,
        "comparison": comparison,
    }

    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
