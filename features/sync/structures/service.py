from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser, get_form_payload
from features.common.cms_utils import post_cms_form
from utils.normalizers import normalize_module_type

from .repository import StructureRepository
from .scraper import (scrape_programs, scrape_school_details,
                      scrape_semester_modules, scrape_semesters,
                      scrape_structures)

logger = get_logger(__name__)


class SchoolSyncService:
    def __init__(self, repository: StructureRepository):
        self.repository = repository
        self._browser = Browser()

    def create_semester(
        self,
        structure_id: int,
        semester_code: str,
        credits: float | None,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        url = f"{BASE_URL}/f_semesteradd.php?showmaster=1&StructureID={structure_id}"

        try:
            progress_callback("Fetching semester add form...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#ff_semesteradd")

            if not form:
                logger.error(
                    f"Could not find semester add form - url={url}, response_length={len(response.text) if response and response.text else 0}"
                )
                return False, "Could not find add form"

            progress_callback("Preparing semester data...")

            form_data = get_form_payload(form)
            form_data["a_add"] = "A"
            form_data["x_StructureID"] = str(structure_id)
            form_data["x_SemesterCode"] = str(semester_code).strip()

            if credits is not None:
                form_data["x_SemesterCredits"] = str(credits)
            else:
                form_data.pop("x_SemesterCredits", None)

            progress_callback("Creating semester in CMS...")
            cms_success, cms_message = post_cms_form(self._browser, url, form_data)

            if not cms_success:
                return False, cms_message

            progress_callback("Refreshing semesters from CMS...")
            semesters = scrape_semesters(structure_id)
            for semester in semesters:
                self.repository.save_semester(
                    int(semester["id"]),
                    str(semester["semester_number"]),
                    str(semester["name"]),
                    float(semester["total_credits"]),
                    structure_id,
                )

            return True, "Semester created successfully"

        except Exception as e:
            logger.error(
                f"Error creating semester - structure_id={structure_id}, semester_code={semester_code}, credits={credits}, error={str(e)}"
            )
            return False, f"Error: {str(e)}"

    def create_semester_module(
        self,
        semester_id: int,
        data: dict,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        url = f"{BASE_URL}/f_semmoduleadd.php?showmaster=1&SemesterID={semester_id}"

        try:
            progress_callback("Fetching semester module add form...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#ff_semmoduleadd")

            if not form:
                logger.error(
                    f"Could not find semester module add form - url={url}, response_length={len(response.text) if response and response.text else 0}"
                )
                return False, "Could not find add form"

            module_id = data.get("module_id")
            module_type = str(data.get("module_type") or "").strip()
            credits = str(data.get("credits") or "").strip()

            if not module_id:
                return False, "Module is required"

            if not module_type:
                return False, "Module type is required"

            if not credits:
                return False, "Credits is required"

            progress_callback("Preparing semester module data...")

            form_data = get_form_payload(form)
            form_data["a_add"] = "A"
            form_data["x_SemesterID"] = str(semester_id)
            form_data["x_ModuleID"] = str(module_id)
            form_data["x_ModuleTypeCode"] = module_type
            form_data["x_SemModuleCredit"] = credits

            if bool(data.get("optional")):
                form_data["x_SemModuleOpt"] = "Y"
            else:
                form_data.pop("x_SemModuleOpt", None)

            remark = str(data.get("remark") or "").strip()
            if remark:
                form_data["x_SemModRemark"] = remark
            else:
                form_data.pop("x_SemModRemark", None)

            prereq_id = data.get("prerequisite_id")
            if prereq_id:
                form_data["x_PreReq"] = str(prereq_id)
            else:
                form_data.pop("x_PreReq", None)

            progress_callback("Creating semester module in CMS...")
            cms_success, cms_message = post_cms_form(self._browser, url, form_data)

            if not cms_success:
                return False, cms_message

            progress_callback("Refreshing semester modules from CMS...")

            semester_modules = scrape_semester_modules(int(semester_id))
            for sem_module in semester_modules:
                normalized_type = normalize_module_type(str(sem_module["type"]))
                self.repository.save_semester_module(
                    int(sem_module["id"]),
                    str(sem_module["module_code"]),
                    str(sem_module["module_name"]),
                    normalized_type,
                    float(sem_module["credits"]),
                    int(semester_id),
                    bool(sem_module["hidden"]),
                )

            return True, "Semester module created successfully"
        except Exception as e:
            logger.error(
                f"Error creating semester module - semester_id={semester_id}, data={data}, error={str(e)}"
            )
            return False, f"Error: {str(e)}"

    def create_structure(
        self,
        program_id: int,
        data: dict,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        url = f"{BASE_URL}/f_structureadd.php?showmaster=1&ProgramID={program_id}"

        try:
            progress_callback("Fetching structure add form...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#ff_structureadd")

            if not form:
                logger.error(
                    f"Could not find structure add form - url={url}, response_length={len(response.text) if response and response.text else 0}"
                )
                return False, "Could not find add form"

            progress_callback("Preparing structure data...")

            form_data = get_form_payload(form)
            form_data["a_add"] = "A"
            form_data["x_ProgramID"] = str(program_id)

            code = (data.get("code") or "").strip()
            desc = (data.get("desc") or "").strip()
            remark = (data.get("remark") or "").strip()

            active = bool(data.get("active", True))
            locked = bool(data.get("locked", False))

            if code:
                form_data["x_StructureCode"] = code
            if desc:
                form_data["x_StructureDesc"] = desc

            if remark:
                form_data["x_StructureRemark"] = remark
            else:
                form_data.pop("x_StructureRemark", None)

            if active:
                form_data["x_StructureActive"] = "Y"
            else:
                form_data.pop("x_StructureActive", None)

            if locked:
                form_data["x_StructureLocked"] = "Y"
            else:
                form_data.pop("x_StructureLocked", None)

            progress_callback("Creating structure in CMS...")
            cms_success, cms_message = post_cms_form(self._browser, url, form_data)

            if not cms_success:
                return False, cms_message

            progress_callback("Refreshing structures from CMS...")
            structures = scrape_structures(program_id)
            for structure in structures:
                self.repository.save_structure(
                    int(structure["id"]),
                    str(structure["code"]),
                    str(structure.get("desc") or ""),
                    program_id,
                )

            return True, "Structure created successfully"

        except Exception as e:
            logger.error(
                f"Error creating structure - program_id={program_id}, data={data}, error={str(e)}"
            )
            return False, f"Error: {str(e)}"

    def fetch_school_and_programs(
        self, school_code: str, progress_callback: Callable[[str, int, int], None]
    ):
        progress_callback(f"Searching for school '{school_code}'...", 1, 2)

        school_data = scrape_school_details(school_code)
        if not school_data:
            raise ValueError(f"School with code '{school_code}' not found")

        school_id = int(school_data["id"])
        school_code = str(school_data["code"])

        progress_callback(
            f"Found school {school_code} (ID: {school_id}). Fetching programs...",
            2,
            2,
        )

        programs = scrape_programs(school_id)

        progress_callback(f"Retrieved {len(programs)} program(s)", 2, 2)

        return school_data, programs

    def import_all_schools_structures(
        self,
        progress_callback: Callable[[str, int, int], None],
        fetch_semesters: bool = False,
    ):
        schools = self.repository.list_active_schools()
        total_schools = len(schools)

        logger.info(f"Starting import for {total_schools} schools")

        for idx, school in enumerate(schools, 1):
            progress_callback(
                f"Processing school {idx}/{total_schools}: {school.name}...",
                idx,
                total_schools,
            )

            programs = scrape_programs(school.id)
            logger.info(f"Found {len(programs)} programs for {school.name}")

            if programs:
                self._import_structures(
                    programs,
                    fetch_semesters,
                    progress_callback,
                )

        progress_callback(
            f"Completed import for {total_schools} school(s)",
            total_schools,
            total_schools,
        )

    def import_school_structures(
        self,
        school_id: int,
        progress_callback: Callable[[str, int, int], None],
        fetch_semesters: bool = False,
    ):
        progress_callback("Fetching programs for school...", 1, 2)

        programs = scrape_programs(school_id)
        logger.info(f"Found {len(programs)} programs for school ID {school_id}")

        if not programs:
            progress_callback("No programs found for this school", 2, 2)
            return

        progress_callback(f"Importing structures for {len(programs)} programs...", 2, 2)

        self._import_structures(
            programs,
            fetch_semesters,
            progress_callback,
        )

        progress_callback(
            f"Completed import for {len(programs)} program(s)",
            2,
            2,
        )

    def import_program_structures(
        self,
        program_id: int,
        progress_callback: Callable[[str, int, int], None],
        fetch_semesters: bool = False,
    ):
        progress_callback("Fetching structures for program...", 1, 2)

        structures = scrape_structures(program_id)
        logger.info(f"Found {len(structures)} structures for program ID {program_id}")

        if not structures:
            progress_callback("No structures found for this program", 2, 2)
            return

        progress_callback(f"Saving {len(structures)} structure(s)...", 2, 2)

        for structure in structures:
            self.repository.save_structure(
                int(structure["id"]),
                str(structure["code"]),
                str(structure["desc"]),
                program_id,
            )

        if fetch_semesters and structures:
            logger.info(
                f"Fetching semesters for {len(structures)} structures of program {program_id}"
            )
            program_code = "Program"
            self._import_semesters(structures, program_code, progress_callback)

        progress_callback(
            f"Completed import for {len(structures)} structure(s)",
            2,
            2,
        )

    def import_school_data(
        self,
        school_data: dict,
        programs: list[dict],
        progress_callback: Callable[[str, int, int], None],
        fetch_structures: bool = False,
        fetch_semesters: bool = False,
    ):
        school_id = int(school_data["id"])
        school_name = str(school_data["name"])
        school_code = str(school_data["code"])

        total_steps = 2
        if fetch_structures:
            total_steps += len(programs)

        current_step = 0

        current_step += 1
        progress_callback(
            f"Saving school {school_code} to database...", current_step, total_steps
        )

        self.repository.save_school(school_id, school_code, school_name)

        current_step += 1
        progress_callback(
            f"Saving {len(programs)} program(s) to database...",
            current_step,
            total_steps,
        )

        for program in programs:
            self.repository.save_program(
                int(program["id"]),
                program["code"],
                program["name"],
                school_id,
                program.get("level", "degree"),
            )

        if fetch_structures:
            logger.info(f"Importing structures for {len(programs)} programs")
            self._import_structures(
                programs, fetch_semesters, progress_callback, current_step, total_steps
            )
        else:
            progress_callback(
                f"Successfully saved {school_code} and {len(programs)} program(s)",
                total_steps,
                total_steps,
            )
            logger.info(
                f"Completed import: {school_code} with {len(programs)} program(s)"
            )

    def _import_structures(
        self,
        programs,
        fetch_semesters: bool,
        progress_callback: Callable[[str, int, int], None],
        current_step=0,
        total_steps=1,
    ):
        logger.info(
            f"Starting to import structures for {len(programs)} programs, fetch_semesters={fetch_semesters}"
        )

        for program in programs:
            current_step += 1
            program_id = int(program["id"])
            program_code = program["code"]

            progress_callback(
                f"Fetching structures for {program_code}...",
                current_step,
                total_steps,
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

    def _import_semesters(
        self,
        structures,
        program_code: str,
        progress_callback: Callable[[str, int, int], None],
    ):
        logger.info(f"Starting to import semesters for {len(structures)} structures")
        for structure in structures:
            structure_id = int(structure["id"])
            structure_code = str(structure["code"])

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
                    str(semester["semester_number"]),
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
        self,
        semesters,
        structure_code: str,
        progress_callback: Callable[[str, int, int], None],
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

                    progress_callback(
                        f"Saving modules for {structure_code}/{semester_name}...",
                        completed,
                        total_semesters,
                    )

                    for sem_module in semester_modules:
                        normalized_type = normalize_module_type(str(sem_module["type"]))
                        self.repository.save_semester_module(
                            int(sem_module["id"]),
                            str(sem_module["module_code"]),
                            str(sem_module["module_name"]),
                            normalized_type,
                            float(sem_module["credits"]),
                            semester_id,
                            bool(sem_module["hidden"]),
                        )

                except Exception as e:
                    logger.error(
                        f"Error importing semester modules for {semester_name}: {e}"
                    )
                    progress_callback(
                        f"Error importing semester modules for {semester_name}",
                        completed,
                        total_semesters,
                    )
