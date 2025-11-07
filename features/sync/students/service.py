from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Callable, Optional

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser, get_form_payload
from features.common.cms_utils import post_cms_form

from .repository import StudentRepository
from .scraper import (
    extract_student_education_ids,
    extract_student_program_ids,
    extract_student_semester_ids,
    scrape_student_data,
    scrape_student_education_data,
    scrape_student_modules_concurrent,
    scrape_student_personal_view,
    scrape_student_program_data,
    scrape_student_semester_data,
    scrape_student_view,
)

if TYPE_CHECKING:
    from features.enrollments.semester import SemesterEnrollmentService

logger = get_logger(__name__)


def today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


class StudentSyncService:
    def __init__(self, repository: Optional[StudentRepository] = None) -> None:
        self._repository = repository or StudentRepository()
        self._browser = Browser()
        self._enrollment_service: Optional[SemesterEnrollmentService] = None

    def _get_enrollment_service(self) -> SemesterEnrollmentService:
        if self._enrollment_service is None:
            from features.enrollments.semester import SemesterEnrollmentService

            self._enrollment_service = SemesterEnrollmentService()
        return self._enrollment_service

    def fetch_student(
        self,
        student_number: str,
        progress_callback: Callable[[str, int, int], None],
        import_options: Optional[dict] = None,
    ) -> bool:
        if import_options is None:
            import_options = {
                "student_info": True,
                "personal_info": True,
                "education_history": True,
                "enrollment_data": True,
            }

        self._repository.preload_all_sponsors()

        total_steps = 3
        student_updated = False
        scraped_data = {}

        if import_options.get("student_info") or import_options.get("personal_info"):
            progress_callback(
                f"Fetching student data for {student_number}...", 1, total_steps
            )

            if import_options.get("student_info"):
                student_data = scrape_student_view(student_number)
                scraped_data.update(student_data)

            if import_options.get("personal_info"):
                personal_data = scrape_student_personal_view(student_number)
                next_of_kin_list = personal_data.pop("next_of_kin", [])
                scraped_data.update(personal_data)

                if next_of_kin_list:
                    self._repository.upsert_next_of_kin(
                        student_number, next_of_kin_list
                    )

            if scraped_data:
                student_updated = self._repository.update_student(
                    student_number, scraped_data
                )

        educations_synced = 0
        educations_failed = 0

        if import_options.get("education_history"):
            progress_callback(
                f"Fetching education records for {student_number}...", 1, total_steps
            )

            education_ids = extract_student_education_ids(student_number)

            for edu_id in education_ids:
                try:
                    education_data = scrape_student_education_data(edu_id)
                    if education_data and education_data.get("std_no"):
                        success, msg = self._repository.upsert_student_education(
                            education_data
                        )
                        if success:
                            educations_synced += 1
                        else:
                            logger.warning(f"Failed to sync education {edu_id}: {msg}")
                            educations_failed += 1
                except Exception as e:
                    logger.error(f"Error syncing education {edu_id}: {str(e)}")
                    educations_failed += 1

        program_ids = []
        if import_options.get("enrollment_data"):
            progress_callback(
                f"Fetching program list for {student_number}...", 2, total_steps
            )
            program_ids = extract_student_program_ids(student_number)

        programs_synced = 0
        programs_failed = 0
        semesters_synced = 0
        semesters_failed = 0
        modules_synced = 0
        modules_failed = 0

        for idx, program_id in enumerate(program_ids, 1):
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

                        try:
                            std_program_id = int(program_id)
                        except (TypeError, ValueError):
                            logger.warning(f"Invalid program ID format: {program_id}")
                            continue

                        semester_ids = extract_student_semester_ids(program_id)

                        structure_id = None
                        if "structure_code" in program_data:
                            structure_id = self._repository.get_structure_by_code(
                                program_data["structure_code"]
                            )

                        if structure_id and semester_ids:
                            self._repository.preload_structure_semesters(structure_id)

                        for sem_idx, sem_id in enumerate(semester_ids, 1):
                            progress_callback(
                                f"Syncing semester {sem_idx} of {len(semester_ids)} "
                                f"for program {idx}/{len(program_ids)} - {student_number}...",
                                2,
                                total_steps,
                            )

                            try:
                                semester_data = scrape_student_semester_data(
                                    sem_id, structure_id, self._repository
                                )
                                if semester_data and semester_data.get("term"):
                                    sem_success, sem_msg, db_semester_id = (
                                        self._repository.upsert_student_semester(
                                            std_program_id, semester_data
                                        )
                                    )
                                    if sem_success and db_semester_id:
                                        semesters_synced += 1

                                        progress_callback(
                                            f"Syncing modules for semester {sem_idx}/{len(semester_ids)} "
                                            f"- program {idx}/{len(program_ids)} - {student_number}...",
                                            2,
                                            total_steps,
                                        )

                                        try:
                                            modules_data = (
                                                scrape_student_modules_concurrent(
                                                    sem_id, db_semester_id
                                                )
                                            )

                                            for module_data in modules_data:
                                                try:
                                                    mod_success, mod_msg = (
                                                        self._repository.upsert_student_module(
                                                            module_data
                                                        )
                                                    )
                                                    if mod_success:
                                                        modules_synced += 1
                                                    else:
                                                        logger.warning(
                                                            f"Failed to sync module {module_data.get('id')}: {mod_msg}"
                                                        )
                                                        modules_failed += 1
                                                except Exception as e:
                                                    logger.error(
                                                        f"Error syncing module {module_data.get('id')}: {str(e)}"
                                                    )
                                                    modules_failed += 1

                                        except Exception as e:
                                            logger.error(
                                                f"Error scraping modules for semester {sem_id}: {str(e)}"
                                            )

                                    else:
                                        logger.warning(
                                            f"Failed to sync semester {sem_id}: {sem_msg}"
                                        )
                                        semesters_failed += 1
                            except Exception as e:
                                logger.error(
                                    f"Error syncing semester {sem_id}: {str(e)}"
                                )
                                semesters_failed += 1

                    else:
                        logger.warning(f"Failed to sync program {program_id}: {msg}")
                        programs_failed += 1
            except Exception as e:
                logger.error(f"Error syncing program {program_id}: {str(e)}")
                programs_failed += 1

        progress_callback(
            f"Completed sync for {student_number}: {educations_synced} education records, "
            f"{programs_synced} programs, {semesters_synced} semesters, {modules_synced} modules synced",
            total_steps,
            total_steps,
        )

        logger.info(
            f"Fetch completed for {student_number}: Student updated={student_updated}, "
            f"Education records synced={educations_synced}, Programs synced={programs_synced}, "
            f"Semesters synced={semesters_synced}, Modules synced={modules_synced}, "
            f"Education records failed={educations_failed}, Programs failed={programs_failed}, "
            f"Semesters failed={semesters_failed}, Modules failed={modules_failed}"
        )

        return student_updated

    def push_student(
        self,
        student_number: str,
        data: dict,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        url = f"{BASE_URL}/r_studentedit.php?StudentID={student_number}"

        try:
            progress_callback(f"Fetching edit form for {student_number}...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#fr_studentedit")

            if not form:
                logger.error(f"Could not find edit form for student {student_number}")
                return False, "Could not find edit form"

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

            progress_callback(f"Pushing {student_number} to CMS...")

            cms_success, cms_message = post_cms_form(self._browser, url, form_data)

            if cms_success:
                progress_callback(f"Saving {student_number} to database...")

                update_success = self._repository.update_student(student_number, data)
                if update_success:
                    return True, "Student updated successfully"
                else:
                    return False, "CMS update succeeded but database update failed"
            else:
                return False, cms_message

        except Exception as e:
            logger.error(f"Error pushing student {student_number}: {str(e)}")
            return False, f"Error: {str(e)}"

    def push_module(
        self,
        std_module_id: int,
        data: dict,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        url = f"{BASE_URL}/r_stdmoduleedit.php?StdModuleID={std_module_id}"

        try:
            progress_callback(f"Fetching edit form for module {std_module_id}...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#fr_stdmoduleedit")

            if not form:
                logger.error(f"Could not find edit form for module {std_module_id}")
                return False, "Could not find edit form"

            progress_callback(f"Preparing data for module {std_module_id}...")

            form_data = get_form_payload(form)

            form_data["a_edit"] = "U"

            if "status" in data and data["status"]:
                form_data["x_StdModStatCode"] = data["status"]

            if "credits" in data and data["credits"]:
                form_data["x_StdModCredits"] = str(data["credits"])

            if "marks" in data and data["marks"]:
                form_data["x_AlterMark"] = str(data["marks"])

            if "grade" in data and data["grade"]:
                form_data["x_AlterGrade"] = str(data["grade"])

            if "semester_module_id" in data and data["semester_module_id"]:
                form_data["x_SemModuleID"] = str(data["semester_module_id"])

            progress_callback(f"Pushing module {std_module_id} to CMS...")

            cms_success, cms_message = post_cms_form(self._browser, url, form_data)

            if cms_success:
                progress_callback(f"Saving module {std_module_id} to database...")

                update_success, msg = self._repository.upsert_student_module(data)
                if update_success:
                    return True, "Module updated successfully"
                else:
                    return (
                        False,
                        f"CMS update succeeded but database update failed: {msg}",
                    )
            else:
                return False, cms_message

        except Exception as e:
            logger.error(f"Error pushing module {std_module_id}: {str(e)}")
            return False, f"Error: {str(e)}"

    def push_semester(
        self,
        data: dict,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        return self._get_enrollment_service().create_semester(data, progress_callback)

    def update_semester(
        self,
        data: dict,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        return self._get_enrollment_service().update_semester(data, progress_callback)

    def push_student_module(
        self,
        student_semester_id: int,
        semester_module_id: int,
        module_status: str,
        module_code: str,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        return self._get_enrollment_service().add_module_to_semester(
            student_semester_id,
            semester_module_id,
            module_status,
            module_code,
            progress_callback,
        )
