from __future__ import annotations

import datetime
from typing import Callable, Optional

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser, get_form_payload

from .repository import ApprovedEnrollmentRepository
from .scraper import get_cms_semester_modules, get_cms_semesters

logger = get_logger(__name__)


def today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


class EnrollmentService:
    def __init__(
        self, repository: Optional[ApprovedEnrollmentRepository] = None
    ) -> None:
        self._repository = repository or ApprovedEnrollmentRepository()
        self._browser = Browser()

    def enroll_students(
        self,
        registration_request_ids: list[int],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> tuple[int, int]:

        success_count = 0
        failed_count = 0

        for idx, request_id in enumerate(registration_request_ids):
            if progress_callback:
                progress_callback(
                    f"Processing registration request {request_id}...",
                    idx + 1,
                    len(registration_request_ids),
                )

            try:
                success = self._enroll_single_request(request_id, progress_callback)

                if success:
                    success_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(f"Error enrolling request {request_id}: {str(e)}")
                failed_count += 1

        return success_count, failed_count

    def _enroll_single_request(
        self,
        request_id: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> bool:
        if progress_callback:
            progress_callback(f"Fetching registration request details...", 0, 100)

        request_details = self._repository.get_registration_request_details(request_id)
        if not request_details:
            logger.error(f"Registration request {request_id} not found")
            return False

        std_no = request_details["std_no"]
        term_name = request_details["term_name"]
        semester_number = request_details["semester_number"]
        semester_status = request_details["semester_status"]

        logger.info(
            f"Enrolling student {std_no} for term {term_name}, semester {semester_number}"
        )

        if progress_callback:
            progress_callback(f"Getting student program for {std_no}...", 10, 100)

        student_program = self._repository.get_active_student_program(std_no)
        if not student_program:
            logger.error(f"No active student program found for student {std_no}")
            return False

        student_program_id = student_program["id"]
        structure_id = student_program["structure_id"]

        logger.info(
            f"Found student program {student_program_id} with structure {structure_id}"
        )

        if progress_callback:
            progress_callback(
                f"Checking CMS for existing semesters for student {std_no}...", 20, 100
            )

        existing_semesters = get_cms_semesters(student_program_id)

        existing_semester_id = None
        for sem in existing_semesters:
            if sem.get("term") == term_name:
                existing_semester_id = sem.get("id")
                logger.info(
                    f"Found existing semester {existing_semester_id} for term {term_name} on CMS"
                )
                break

        if existing_semester_id:
            student_semester_id = existing_semester_id
            logger.info(f"Reusing existing semester {student_semester_id}")

            if progress_callback:
                progress_callback(
                    f"Reusing existing semester for student {std_no}...", 40, 100
                )
        else:
            logger.info(f"Creating new semester for student {std_no}, term {term_name}")

            if progress_callback:
                progress_callback(
                    f"Getting structure semester for student {std_no}...", 30, 100
                )

            structure_semester_id = self._repository.get_structure_semester_by_number(
                structure_id, semester_number
            )
            if not structure_semester_id:
                logger.error(
                    f"Structure semester not found for structure {structure_id}, semester {semester_number}"
                )
                return False

            if progress_callback:
                progress_callback(
                    f"Creating semester on CMS for student {std_no}...", 35, 100
                )

            created_sem_id = self._create_semester_on_cms(
                student_program_id,
                structure_id,
                term_name,
                structure_semester_id,
                semester_status,
                today(),
            )

            if not created_sem_id:
                logger.error(f"Failed to create semester on CMS for student {std_no}")
                return False

            student_semester_id = created_sem_id
            logger.info(f"Created new semester {student_semester_id} on CMS")

            if progress_callback:
                progress_callback(
                    f"Saving semester to database for student {std_no}...", 40, 100
                )

            self._repository.upsert_student_semester(
                student_program_id,
                {
                    "id": student_semester_id,
                    "term": term_name,
                    "semester_number": semester_number,
                    "status": semester_status,
                    "caf_date": today(),
                },
            )

        if progress_callback:
            progress_callback(
                f"Checking existing modules for student {std_no}...", 50, 100
            )

        existing_modules = get_cms_semester_modules(student_semester_id)
        existing_module_codes = {mod["module_code"] for mod in existing_modules}

        requested_modules = self._repository.get_requested_modules(request_id)

        modules_added = 0
        modules_skipped = 0
        modules_failed = 0
        total_modules = len(requested_modules)

        for idx, req_mod in enumerate(requested_modules, 1):
            module_code = req_mod.module_code
            module_status = req_mod.module_status
            semester_module_id = req_mod.semester_module_id
            credits = req_mod.credits or 0

            progress_percent = 50 + int((idx / total_modules) * 40)

            if module_code in existing_module_codes:
                logger.info(
                    f"Module {module_code} already exists in semester {student_semester_id}, skipping"
                )
                modules_skipped += 1

                if progress_callback:
                    progress_callback(
                        f"Module {module_code} already exists, skipping ({idx}/{total_modules})...",
                        progress_percent,
                        100,
                    )
                continue

            logger.info(
                f"Adding module {module_code} (SemModuleID={semester_module_id}) to semester {student_semester_id}"
            )

            if progress_callback:
                progress_callback(
                    f"Adding module {module_code} to CMS ({idx}/{total_modules})...",
                    progress_percent,
                    100,
                )

            success = self._add_module_to_cms_semester(
                student_semester_id, semester_module_id, module_status, credits
            )

            if success:
                modules_added += 1

                if progress_callback:
                    progress_callback(
                        f"Syncing module {module_code} to database ({idx}/{total_modules})...",
                        progress_percent,
                        100,
                    )

                new_modules = get_cms_semester_modules(student_semester_id)
                for new_mod in new_modules:
                    if (
                        new_mod["module_code"] == module_code
                        and new_mod["id"] not in existing_module_codes
                    ):
                        self._repository.upsert_student_module(
                            {
                                "id": new_mod["id"],
                                "semester_module_id": semester_module_id,
                                "status": module_status,
                                "marks": "NM",
                                "grade": "NM",
                                "student_semester_id": student_semester_id,
                            }
                        )
                        break
            else:
                logger.error(
                    f"Failed to add module {module_code} to semester {student_semester_id}"
                )
                modules_failed += 1

        logger.info(
            f"Enrollment complete for request {request_id}: "
            f"{modules_added} modules added, {modules_skipped} skipped, {modules_failed} failed"
        )

        if progress_callback:
            progress_callback(f"Finalizing enrollment for student {std_no}...", 95, 100)

        if modules_failed == 0:
            self._repository.update_registration_request_status(
                request_id, "registered"
            )
            logger.info(f"Marked registration request {request_id} as registered")

            if progress_callback:
                progress_callback(f"Enrollment complete for student {std_no}", 100, 100)
            return True
        else:
            logger.warning(
                f"Request {request_id} partially completed with {modules_failed} failures"
            )
            return False

    def _create_semester_on_cms(
        self,
        student_program_id: int,
        structure_id: int,
        term: str,
        structure_semester_id: int,
        status: str,
        caf_date: str,
    ) -> Optional[int]:
        url = f"{BASE_URL}/r_stdsemesteradd.php?StdProgramID={student_program_id}"

        try:
            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#fr_stdsemesteradd")

            if not form:
                logger.error("Could not find semester add form")
                return None

            form_data = get_form_payload(form)

            form_data["a_add"] = "A"
            form_data["x_StdProgramID"] = str(student_program_id)
            form_data["x_StructureID"] = str(structure_id)
            form_data["x_CampusCode"] = "Lesotho"
            form_data["x_TermCode"] = term
            form_data["x_SemesterID"] = str(structure_semester_id)
            form_data["x_SemesterStatus"] = status
            form_data["x_StdSemCAFDate"] = caf_date

            logger.info(f"Posting new semester for program {student_program_id}")
            post_response = self._browser.post(url, form_data)

            if "Successful" not in post_response.text:
                logger.error("CMS semester creation did not return 'Successful'")
                return None

            logger.info(
                f"Successfully posted semester for program {student_program_id}"
            )

            semesters = get_cms_semesters(student_program_id)
            for sem in semesters:
                if sem.get("term") == term:
                    logger.info(f"Found created semester ID: {sem['id']}")
                    return sem["id"]

            logger.error("Could not find created semester in CMS list")
            return None

        except Exception as e:
            logger.error(f"Error creating semester on CMS: {str(e)}")
            return None

    def _add_module_to_cms_semester(
        self,
        student_semester_id: int,
        semester_module_id: int,
        module_status: str,
        credits: float,
    ) -> bool:
        try:
            self._browser.fetch(
                f"{BASE_URL}/r_stdmodulelist.php?showmaster=1&StdSemesterID={student_semester_id}"
            )

            add_response = self._browser.fetch(f"{BASE_URL}/r_stdmoduleadd1.php")
            page = BeautifulSoup(add_response.text, "lxml")

            form_data = get_form_payload(page)

            module_string = f"{semester_module_id}-{module_status}-{credits}-1200"

            form_data["Submit"] = "Add+Modules"
            form_data["take[]"] = [module_string]

            logger.info(
                f"Posting module {semester_module_id} to semester {student_semester_id}"
            )
            self._browser.post(f"{BASE_URL}/r_stdmoduleadd1.php", form_data)

            verify_response = self._browser.fetch(
                f"{BASE_URL}/r_stdmodulelist.php?showmaster=1&StdSemesterID={student_semester_id}"
            )
            verify_page = BeautifulSoup(verify_response.text, "lxml")
            module_table = verify_page.select_one("table#ewlistmain")

            if not module_table:
                logger.error("Could not find module list after adding module")
                return False

            logger.info(
                f"Successfully added module {semester_module_id} to semester {student_semester_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error adding module to CMS semester: {str(e)}")
            return False
