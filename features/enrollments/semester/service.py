from __future__ import annotations

import datetime
from typing import Callable, Optional

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser, get_form_payload
from features.common.cms_utils import format_module_enrollment_string, post_cms_form

from .repository import SemesterEnrollmentRepository
from .scraper import (
    extract_student_semester_ids,
    scrape_student_modules_concurrent,
    scrape_student_semester_data,
)

logger = get_logger(__name__)


def today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


class SemesterEnrollmentService:
    def __init__(
        self, repository: Optional[SemesterEnrollmentRepository] = None
    ) -> None:
        self._repository = repository or SemesterEnrollmentRepository()
        self._browser = Browser()

    def create_semester_on_cms(
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
            success, _ = post_cms_form(self._browser, url, form_data)

            if not success:
                logger.error("CMS semester creation did not return 'Successful'")
                return None

            logger.info(
                f"Successfully posted semester for program {student_program_id}"
            )

            # Find the created semester ID by term
            from .scraper import extract_student_semester_ids

            semester_ids = extract_student_semester_ids(str(student_program_id))
            for sem_id in semester_ids:
                sem_data = scrape_student_semester_data(sem_id)
                if sem_data.get("term") == term:
                    logger.info(f"Found created semester ID: {sem_id}")
                    return sem_id

            logger.error("Could not find created semester in CMS list")
            return None

        except Exception as e:
            logger.error(f"Error creating semester on CMS: {str(e)}")
            return None

    def create_semester(
        self,
        data: dict,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        student_program_id = data.get("student_program_id")
        if not student_program_id:
            return False, "Missing student_program_id"

        try:
            progress_callback(f"Fetching add form for semester...")

            program_details = self._repository.get_student_program_details_by_id(
                student_program_id
            )

            if not program_details or not program_details.get("structure_id"):
                return False, "Student program or structure not found"

            structure_id = program_details["structure_id"]
            term = data.get("term", "")
            structure_semester_id = data.get("structure_semester_id", 0)
            status = data.get("status", "Active")
            caf_date = data.get("caf_date", today())

            progress_callback(f"Preparing semester data...")
            progress_callback(f"Pushing semester to CMS...")

            matching_semester_id = self.create_semester_on_cms(
                student_program_id,
                structure_id,
                term,
                structure_semester_id,
                status,
                caf_date,
            )

            if not matching_semester_id:
                logger.error(
                    f"Could not find created semester ID for term {data.get('term')}"
                )
                return (
                    False,
                    f"CMS update succeeded but could not retrieve created semester ID",
                )

            progress_callback(f"Saving semester to database...")

            db_data = {
                "id": matching_semester_id,
                "term": data.get("term"),
                "status": data.get("status"),
                "caf_date": data.get("caf_date"),
            }

            if "structure_semester_id" in data and data["structure_semester_id"]:
                db_data["structure_semester_id"] = data["structure_semester_id"]

            update_success, msg, _ = self._repository.upsert_student_semester(
                student_program_id, db_data
            )
            if update_success:
                return True, "Semester added successfully"
            else:
                return (
                    False,
                    f"CMS update succeeded but database update failed: {msg}",
                )

        except Exception as e:
            logger.error(f"Error creating semester: {str(e)}")
            return False, f"Error: {str(e)}"

    def update_semester(
        self,
        data: dict,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        student_semester_id = data.get("student_semester_id")
        if not student_semester_id:
            return False, "Missing student_semester_id"

        url = f"{BASE_URL}/r_stdsemesteredit.php?StdSemesterID={student_semester_id}"

        try:
            progress_callback(f"Fetching edit form for semester...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#fr_stdsemesteredit")

            if not form:
                logger.error(
                    f"Could not find edit form for semester {student_semester_id}"
                )
                return False, "Could not find edit form"

            progress_callback(f"Preparing semester data...")

            form_data = get_form_payload(form)

            form_data["a_edit"] = "U"
            form_data["btnAction"] = "Edit"
            form_data["x_CampusCode"] = "Lesotho"

            semester_data = self._repository.get_student_semester_by_id(
                student_semester_id
            )
            if not semester_data:
                return False, "Semester not found in database"

            current_term = semester_data.get("term")
            structure_id = semester_data.get("structure_id")

            if structure_id:
                form_data["x_StructureID"] = str(structure_id)

            if "structure_semester_id" in data and data["structure_semester_id"]:
                form_data["x_SemesterID"] = str(data["structure_semester_id"])

            if "status" in data and data["status"]:
                form_data["x_SemesterStatus"] = data["status"]

            # Step 1: Update without term (CMS quirk)
            progress_callback(f"Pushing semester update to CMS (step 1)...")

            logger.info(
                f"Posting update for semester {student_semester_id} (without term)"
            )
            form_data["x_TermCode"] = ""
            success, message = post_cms_form(self._browser, url, form_data)

            if not success:
                logger.error(f"CMS update failed for semester {student_semester_id}")
                return False, message

            # Step 2: Update with term
            progress_callback(f"Fetching edit form again for semester...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#fr_stdsemesteredit")

            if not form:
                logger.error(f"Could not find edit form for second update")
                return False, "Could not find edit form for second update"

            progress_callback(f"Preparing semester data for step 2...")

            form_data = get_form_payload(form)

            form_data["a_edit"] = "U"
            form_data["btnAction"] = "Edit"
            form_data["x_CampusCode"] = "Lesotho"

            if structure_id:
                form_data["x_StructureID"] = str(structure_id)

            if current_term:
                form_data["x_TermCode"] = current_term

            if "structure_semester_id" in data and data["structure_semester_id"]:
                form_data["x_SemesterID"] = str(data["structure_semester_id"])

            if "status" in data and data["status"]:
                form_data["x_SemesterStatus"] = data["status"]

            progress_callback(f"Pushing semester update to CMS (step 2)...")

            logger.info(
                f"Posting update for semester {student_semester_id} (with term)"
            )
            success, message = post_cms_form(self._browser, url, form_data)

            if not success:
                logger.error(f"CMS update failed for semester {student_semester_id}")
                return False, message

            logger.info(f"Successfully posted semester {student_semester_id} to CMS")

            progress_callback(f"Saving semester to database...")

            db_data = {
                "id": student_semester_id,
                "status": data.get("status"),
            }

            if "structure_semester_id" in data and data["structure_semester_id"]:
                db_data["structure_semester_id"] = data["structure_semester_id"]

            update_success, msg, _ = self._repository.upsert_student_semester(
                semester_data["student_program_id"], db_data
            )
            if update_success:
                return True, "Semester updated successfully"
            else:
                return (
                    False,
                    f"CMS update succeeded but database update failed: {msg}",
                )

        except Exception as e:
            logger.error(f"Error updating semester: {str(e)}")
            return False, f"Error: {str(e)}"

    def add_module_to_semester(
        self,
        student_semester_id: int,
        semester_module_id: int,
        module_status: str,
        module_code: str,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        try:
            progress_callback(f"Fetching add module form...")

            self._browser.fetch(
                f"{BASE_URL}/r_stdmodulelist.php?showmaster=1&StdSemesterID={student_semester_id}"
            )

            progress_callback(f"Navigating to module add page...")

            add_response = self._browser.fetch(f"{BASE_URL}/r_stdmoduleadd1.php")
            page = BeautifulSoup(add_response.text, "lxml")

            form_data = get_form_payload(page)

            progress_callback(f"Fetching module details...")

            credits = self._repository.get_semester_module_credits(semester_module_id)

            if credits is None:
                return False, "Semester module not found in database"

            # Use the shared utility function for module string formatting
            module_string = format_module_enrollment_string(
                semester_module_id, module_status, int(credits)
            )

            form_data["Submit"] = "Add+Modules"
            form_data["take[]"] = [module_string]

            progress_callback(f"Pushing module to CMS...")

            logger.info(
                f"Posting module {semester_module_id} to semester {student_semester_id}"
            )
            self._browser.post(f"{BASE_URL}/r_stdmoduleadd1.php", form_data)

            progress_callback(f"Verifying module was added...")

            verify_response = self._browser.fetch(
                f"{BASE_URL}/r_stdmodulelist.php?showmaster=1&StdSemesterID={student_semester_id}"
            )
            verify_page = BeautifulSoup(verify_response.text, "lxml")
            module_table = verify_page.select_one("table#ewlistmain")

            if not module_table:
                logger.error("Could not find module list after adding module")
                return False, "Could not verify module was added"

            module_rows = module_table.select("tr.ewTableRow, tr.ewTableAltRow")

            if not module_rows:
                logger.error("No modules found after adding")
                return False, "Module was not added"

            progress_callback(f"Syncing new module to database...")

            modules_data = scrape_student_modules_concurrent(
                str(student_semester_id), student_semester_id
            )

            added_module_data = None
            for module_data in modules_data:
                if module_data.get("module_code") == module_code:
                    added_module_data = module_data
                    break

            if not added_module_data:
                logger.error(
                    f"Could not find newly added module {module_code} in scraped data"
                )
                return False, "Module added but could not sync to database"

            success, msg = self._repository.upsert_student_module(added_module_data)
            if success:
                logger.info(
                    f"Successfully added module {semester_module_id} to semester {student_semester_id}"
                )
                return True, "Module added successfully"
            else:
                return False, f"Module added to CMS but database sync failed: {msg}"

        except Exception as e:
            logger.error(f"Error adding module to semester: {str(e)}")
            return False, f"Error: {str(e)}"

    def add_modules_batch(
        self,
        student_semester_id: int,
        modules_data: list[dict],
    ) -> bool:
        if not modules_data:
            logger.info(f"No modules to push for semester {student_semester_id}")
            return True

        try:
            logger.info(
                f"Pushing {len(modules_data)} modules to semester {student_semester_id}"
            )

            # Navigate to module list page
            self._browser.fetch(
                f"{BASE_URL}/r_stdmodulelist.php?showmaster=1&StdSemesterID={student_semester_id}"
            )

            # Navigate to add module page
            add_response = self._browser.fetch(f"{BASE_URL}/r_stdmoduleadd1.php")
            page = BeautifulSoup(add_response.text, "lxml")

            # Build module strings
            modules_with_amounts = []
            for module_data in modules_data:
                semester_module_id = module_data["semester_module_id"]
                module_status = module_data["module_status"]
                credits = module_data["credits"]
                module_string = format_module_enrollment_string(
                    semester_module_id, module_status, int(credits)
                )
                modules_with_amounts.append(module_string)

            if not modules_with_amounts:
                logger.warning("No valid modules to push")
                return False

            # Submit batch
            form_data = get_form_payload(page)
            form_data["Submit"] = "Add+Modules"
            form_data["take[]"] = modules_with_amounts

            logger.info(
                f"Posting batch of {len(modules_with_amounts)} modules to semester {student_semester_id}"
            )
            self._browser.post(f"{BASE_URL}/r_stdmoduleadd1.php", form_data)

            return True

        except Exception as e:
            logger.error(f"Error adding batch modules to CMS semester: {str(e)}")
            return False
