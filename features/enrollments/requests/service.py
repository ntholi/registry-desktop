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
            progress_callback(f"Fetching enrollment data...", 0, 100)

        enrollment_data = self._repository.get_enrollment_data(request_id)
        if not enrollment_data:
            logger.error(f"Registration request {request_id} not found")
            return False

        std_no = enrollment_data["std_no"]
        term_name = enrollment_data["term_name"]
        semester_number = enrollment_data["semester_number"]
        semester_status = enrollment_data["semester_status"]
        student_program_id = enrollment_data["student_program_id"]
        structure_id = enrollment_data["structure_id"]
        requested_modules = enrollment_data["modules"]

        if not student_program_id or not structure_id:
            logger.error(f"No active student program found for student {std_no}")
            return False

        logger.info(
            f"Enrolling student {std_no} for term {term_name}, semester {semester_number}"
        )
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

        modules_to_push = []
        modules_skipped = 0

        for req_mod in requested_modules:
            module_code = req_mod.module_code
            module_status = req_mod.module_status
            semester_module_id = req_mod.semester_module_id
            credits = req_mod.credits or 0

            if module_code in existing_module_codes:
                logger.info(
                    f"Module {module_code} already exists in semester {student_semester_id}, skipping"
                )
                modules_skipped += 1
            else:
                modules_to_push.append(
                    {
                        "module_code": module_code,
                        "semester_module_id": semester_module_id,
                        "module_status": module_status,
                        "credits": credits,
                    }
                )

        if modules_to_push:
            if progress_callback:
                progress_callback(
                    f"Pushing {len(modules_to_push)} modules to CMS in batch...",
                    60,
                    100,
                )

            logger.info(
                f"Pushing {len(modules_to_push)} modules to semester {student_semester_id} "
                f"({modules_skipped} already exist)"
            )

            registered_module_codes = self._add_modules_to_cms_semester(
                student_semester_id, modules_to_push
            )

            if progress_callback:
                progress_callback(
                    f"Syncing {len(registered_module_codes)} modules to database...",
                    80,
                    100,
                )

            updated_modules = get_cms_semester_modules(student_semester_id)
            modules_added = 0

            for req_mod in requested_modules:
                module_code = req_mod.module_code
                semester_module_id = req_mod.semester_module_id
                module_status = req_mod.module_status

                if module_code in existing_module_codes:
                    continue

                for cms_mod in updated_modules:
                    if cms_mod["module_code"] == module_code:
                        self._repository.upsert_student_module(
                            {
                                "id": cms_mod["id"],
                                "semester_module_id": semester_module_id,
                                "status": module_status,
                                "marks": "NM",
                                "grade": "NM",
                                "student_semester_id": student_semester_id,
                            }
                        )
                        modules_added += 1
                        break

            modules_failed = len(modules_to_push) - modules_added

            logger.info(
                f"Enrollment complete for request {request_id}: "
                f"{modules_added} modules added, {modules_skipped} skipped, {modules_failed} failed"
            )
        else:
            modules_added = 0
            modules_failed = 0
            logger.info(
                f"All {modules_skipped} modules already exist on website for request {request_id}"
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

    def _add_modules_to_cms_semester(
        self,
        student_semester_id: int,
        modules_data: list[dict],
    ) -> list[str]:

        if not modules_data:
            logger.info(f"No modules to push for semester {student_semester_id}")
            return []

        try:
            existing_modules = get_cms_semester_modules(student_semester_id)
            existing_module_codes = {mod["module_code"] for mod in existing_modules}

            if existing_module_codes:
                logger.info(
                    f"Found {len(existing_module_codes)} modules already on website: {existing_module_codes}"
                )

            modules_to_push = []
            for module_data in modules_data:
                module_code = module_data["module_code"]
                if module_code not in existing_module_codes:
                    modules_to_push.append(module_data)
                else:
                    logger.info(
                        f"Module {module_code} already exists in semester {student_semester_id}, skipping"
                    )

            if not modules_to_push:
                logger.info("All modules already exist on website, skipping batch push")
                return list(existing_module_codes)

            logger.info(
                f"Will push {len(modules_to_push)} new modules "
                f"(skipping {len(modules_data) - len(modules_to_push)} already on website)"
            )

            self._browser.fetch(
                f"{BASE_URL}/r_stdmodulelist.php?showmaster=1&StdSemesterID={student_semester_id}"
            )

            add_response = self._browser.fetch(f"{BASE_URL}/r_stdmoduleadd1.php")
            page = BeautifulSoup(add_response.text, "lxml")

            modules_with_amounts = []
            for module_data in modules_to_push:
                semester_module_id = module_data["semester_module_id"]
                module_status = module_data["module_status"]
                credits = module_data["credits"]
                module_string = f"{semester_module_id}-{module_status}-{credits}-1200"
                modules_with_amounts.append(module_string)

            if not modules_with_amounts:
                logger.warning("No valid modules to push after filtering")
                return list(existing_module_codes)

            form_data = get_form_payload(page)
            form_data["Submit"] = "Add+Modules"
            form_data["take[]"] = modules_with_amounts

            logger.info(
                f"Posting batch of {len(modules_with_amounts)} modules to semester {student_semester_id}"
            )
            self._browser.post(f"{BASE_URL}/r_stdmoduleadd1.php", form_data)

            updated_modules = get_cms_semester_modules(student_semester_id)
            updated_module_codes = [mod["module_code"] for mod in updated_modules]

            logger.info(
                f"Successfully pushed batch modules - total on website: {len(updated_module_codes)}"
            )

            return updated_module_codes

        except Exception as e:
            logger.error(f"Error adding batch modules to CMS semester: {str(e)}")
            return []
