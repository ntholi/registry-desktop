from __future__ import annotations

from typing import Callable, Optional

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser, get_form_payload

from .repository import StudentRepository
from .scraper import (
    extract_student_program_ids,
    scrape_student_data,
    scrape_student_program_data,
)

logger = get_logger(__name__)


class StudentSyncService:
    def __init__(self, repository: Optional[StudentRepository] = None) -> None:
        self._repository = repository or StudentRepository()
        self._browser = Browser()

    def pull_student(
        self,
        student_number: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> bool:
        total_steps = 3

        if progress_callback:
            progress_callback(
                f"Fetching personal data for {student_number}...", 1, total_steps
            )

        scraped_data = scrape_student_data(student_number)
        if not scraped_data:
            return False

        student_updated = self._repository.update_student(student_number, scraped_data)

        if progress_callback:
            progress_callback(
                f"Fetching program list for {student_number}...", 2, total_steps
            )

        program_ids = extract_student_program_ids(student_number)

        programs_synced = 0
        programs_failed = 0

        for idx, program_id in enumerate(program_ids, 1):
            if progress_callback:
                progress_callback(
                    f"Syncing program {idx} of {len(program_ids)} for {student_number}...",
                    2,
                    total_steps,
                )

            try:
                program_data = scrape_student_program_data(program_id)
                if program_data and "std_no" in program_data:
                    success, msg = self._repository.upsert_student_program(
                        program_id, program_data["std_no"], program_data
                    )
                    if success:
                        programs_synced += 1
                    else:
                        logger.warning(f"Failed to sync program {program_id}: {msg}")
                        programs_failed += 1
            except Exception as e:
                logger.error(f"Error syncing program {program_id}: {str(e)}")
                programs_failed += 1

        if progress_callback:
            progress_callback(
                f"Completed sync for {student_number}: {programs_synced} programs synced, {programs_failed} failed",
                total_steps,
                total_steps,
            )

        logger.info(
            f"Pull completed for {student_number}: Student updated={student_updated}, "
            f"Programs synced={programs_synced}, Failed={programs_failed}"
        )

        return student_updated

    def push_student(
        self,
        student_number: str,
        data: dict,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, str]:
        url = f"{BASE_URL}/r_studentedit.php?StudentID={student_number}"

        try:
            if progress_callback:
                progress_callback(f"Fetching edit form for {student_number}...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#fr_studentedit")

            if not form:
                logger.error(f"Could not find edit form for student {student_number}")
                return False, "Could not find edit form"

            if progress_callback:
                progress_callback(f"Preparing data for {student_number}...")

            form_data = get_form_payload(form)

            form_data["a_edit"] = "U"
            form_data["x_InstitutionID"] = "1"

            program_details = self._repository.get_student_program_details(
                student_number
            )

            if program_details:
                if program_details.get("school_id"):
                    form_data["x_SchoolID"] = str(program_details["school_id"])
                    form_data["x_opSchoolID"] = str(program_details["school_id"])

                if program_details.get("program_id"):
                    form_data["x_ProgramID"] = str(program_details["program_id"])
                    form_data["x_opProgramID"] = str(program_details["program_id"])

                if program_details.get("structure_id"):
                    form_data["x_StructureID"] = str(program_details["structure_id"])

                if program_details.get("intake_date"):
                    form_data["x_IntakeDateCode"] = program_details["intake_date"]

                if program_details.get("start_term"):
                    form_data["x_opTermCode"] = program_details["start_term"]

            if "name" in data:
                form_data["x_StudentName"] = data["name"]

            if "gender" in data:
                gender_input = form.select_one("input[name='x_Sex']")
                if gender_input:
                    form_data["x_Sex"] = data["gender"]

            if data.get("date_of_birth"):
                dob = data["date_of_birth"]
                birthdate_input = form.select_one("input[name='x_Birthdate']")
                if birthdate_input:
                    if hasattr(dob, "strftime"):
                        form_data["x_Birthdate"] = dob.strftime("%Y-%m-%d")
                    else:
                        form_data["x_Birthdate"] = str(dob)

            if "email" in data:
                form_data["x_StdEmail"] = data["email"]

            if "phone1" in data:
                form_data["x_StdContactNo"] = data["phone1"]

            if "phone2" in data:
                form_data["x_StdContactNo2"] = data["phone2"]

            if "national_id" in data:
                form_data["x_StudentNo"] = data["national_id"]

            if progress_callback:
                progress_callback(f"Pushing {student_number} to CMS...")

            logger.info(f"Posting update for student {student_number}")
            post_response = self._browser.post(url, form_data)

            if "Successful" in post_response.text:
                logger.info(f"Successfully posted student {student_number} to web")

                if progress_callback:
                    progress_callback(f"Saving {student_number} to database...")

                update_success = self._repository.update_student(student_number, data)
                if update_success:
                    return True, "Student updated successfully"
                else:
                    return False, "Web update succeeded but database update failed"
            else:
                logger.error(f"Web update failed for student {student_number}")
                return (
                    False,
                    "Web update failed - response did not contain 'Successful'",
                )

        except Exception as e:
            logger.error(f"Error pushing student {student_number}: {str(e)}")
            return False, f"Error: {str(e)}"
