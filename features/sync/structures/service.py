from concurrent.futures import ThreadPoolExecutor, as_completed

from base import get_logger

from .repository import StructureRepository
from .scraper import (
    scrape_programs,
    scrape_school_details,
    scrape_semester_modules,
    scrape_semesters,
    scrape_structures,
)

logger = get_logger(__name__)


class SchoolSyncService:
    def __init__(self, repository: StructureRepository):
        self.repository = repository

    def import_school(
        self,
        school_code: str,
        fetch_structures: bool = False,
        fetch_semesters: bool = False,
        progress_callback=None,
    ):
        if progress_callback:
            progress_callback(f"Searching for school '{school_code}'...", 1, 4)

        school_data = scrape_school_details(school_code)
        if not school_data:
            raise ValueError(f"School with code '{school_code}' not found")

        school_id = int(school_data["id"])
        school_name = str(school_data["name"])
        school_code = str(school_data["code"])

        if progress_callback:
            progress_callback(
                f"Found school {school_code} (ID: {school_id}). Fetching programs...",
                2,
                4,
            )

        programs = scrape_programs(school_id)

        if progress_callback:
            progress_callback(
                f"Retrieved {len(programs)} program(s). Saving to database...", 3, 4
            )

        self.repository.save_school(school_id, school_code, school_name)

        for program in programs:
            self.repository.save_program(
                int(program["id"]),
                program["code"],
                program["name"],
                school_id,
            )

        if fetch_structures:
            if progress_callback:
                progress_callback(
                    f"Fetching structures for {len(programs)} program(s)...", 4, 4
                )
            self._import_structures(programs, fetch_semesters, progress_callback)
        else:
            if progress_callback:
                progress_callback(
                    f"Successfully saved {school_code} and {len(programs)} program(s)",
                    4,
                    4,
                )

        return school_id, programs

    def _import_structures(
        self, programs, fetch_semesters: bool, progress_callback=None
    ):
        total_programs = len(programs)
        current_program = 0

        logger.info(
            f"Starting to import structures for {total_programs} programs, fetch_semesters={fetch_semesters}"
        )

        for program in programs:
            current_program += 1
            program_id = int(program["id"])
            program_code = program["code"]

            if progress_callback:
                progress_callback(
                    f"Fetching structures for {program_code}...",
                    current_program,
                    total_programs,
                )

            structures = scrape_structures(program_id)
            logger.info(
                f"Found {len(structures)} structures for program {program_code}"
            )

            for structure in structures:
                self.repository.save_structure(
                    int(structure["id"]),
                    str(structure["code"]),
                    str(structure["desc"]),
                    program_id,
                )

            if fetch_semesters and structures:
                logger.info(
                    f"Fetching semesters for {len(structures)} structures of program {program_code}"
                )
                self._import_semesters(structures, program_code, progress_callback)

    def _import_semesters(self, structures, program_code: str, progress_callback=None):
        logger.info(f"Starting to import semesters for {len(structures)} structures")
        for structure in structures:
            structure_id = int(structure["id"])
            structure_code = str(structure["code"])

            if progress_callback:
                progress_callback(
                    f"Fetching semesters for {program_code}/{structure_code}...",
                    0,
                    1,
                )

            semesters = scrape_semesters(structure_id)
            logger.info(
                f"Found {len(semesters)} semesters for structure {structure_code}"
            )

            for semester in semesters:
                self.repository.save_semester(
                    int(semester["id"]),
                    int(semester["semester_number"]),
                    str(semester["name"]),
                    float(semester["total_credits"]),
                    structure_id,
                )

            if semesters:
                logger.info(
                    f"Fetching modules for {len(semesters)} semesters of structure {structure_code}"
                )
                self._import_semester_modules_concurrent(
                    semesters, structure_code, progress_callback
                )

    def _import_semester_modules_concurrent(
        self, semesters, structure_code: str, progress_callback=None
    ):
        total_semesters = len(semesters)

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_semester = {
                executor.submit(scrape_semester_modules, int(semester["id"])): semester
                for semester in semesters
            }

            completed = 0
            for future in as_completed(future_to_semester):
                semester = future_to_semester[future]
                semester_name = str(semester["name"])
                semester_id = int(semester["id"])

                try:
                    semester_modules = future.result()
                    completed += 1

                    if progress_callback:
                        progress_callback(
                            f"Saving modules for {structure_code}/{semester_name}...",
                            completed,
                            total_semesters,
                        )

                    for sem_module in semester_modules:
                        self.repository.save_semester_module(
                            int(sem_module["id"]),
                            str(sem_module["module_code"]),
                            str(sem_module["module_name"]),
                            str(sem_module["type"]),
                            float(sem_module["credits"]),
                            semester_id,
                            bool(sem_module["hidden"]),
                        )

                except Exception as e:
                    logger.error(
                        f"Error importing semester modules for {semester_name}: {e}"
                    )
                    if progress_callback:
                        progress_callback(
                            f"Error importing semester modules for {semester_name}",
                            completed,
                            total_semesters,
                        )
