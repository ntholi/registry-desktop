from __future__ import annotations

import datetime
from typing import Callable, Optional

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser, get_form_payload

from .repository import StudentRepository
from .scraper import (
    extract_student_program_ids,
    extract_student_semester_ids,
    scrape_student_data,
    scrape_student_modules_concurrent,
    scrape_student_program_data,
    scrape_student_semester_data,
)

logger = get_logger(__name__)


def today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


class StudentSyncService:
    def __init__(self, repository: Optional[StudentRepository] = None) -> None:
        self._repository = repository or StudentRepository()
        self._browser = Browser()

    def fetch_student(
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
        semesters_synced = 0
        semesters_failed = 0
        modules_synced = 0
        modules_failed = 0

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

                        try:
                            std_program_id = int(program_id)
                        except (TypeError, ValueError):
                            logger.warning(f"Invalid program ID format: {program_id}")
                            continue

                        semester_ids = extract_student_semester_ids(program_id)

                        for sem_idx, sem_id in enumerate(semester_ids, 1):
                            if progress_callback:
                                progress_callback(
                                    f"Syncing semester {sem_idx} of {len(semester_ids)} "
                                    f"for program {idx}/{len(program_ids)} - {student_number}...",
                                    2,
                                    total_steps,
                                )

                            try:
                                semester_data = scrape_student_semester_data(sem_id)
                                if semester_data and semester_data.get("term"):
                                    sem_success, sem_msg, db_semester_id = (
                                        self._repository.upsert_student_semester(
                                            std_program_id, semester_data
                                        )
                                    )
                                    if sem_success and db_semester_id:
                                        semesters_synced += 1

                                        if progress_callback:
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

        if progress_callback:
            progress_callback(
                f"Completed sync for {student_number}: {programs_synced} programs, "
                f"{semesters_synced} semesters, {modules_synced} modules synced",
                total_steps,
                total_steps,
            )

        logger.info(
            f"Fetch completed for {student_number}: Student updated={student_updated}, "
            f"Programs synced={programs_synced}, Semesters synced={semesters_synced}, "
            f"Modules synced={modules_synced}, "
            f"Programs failed={programs_failed}, Semesters failed={semesters_failed}, "
            f"Modules failed={modules_failed}"
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
                logger.info(f"Successfully posted student {student_number} to CMS")

                if progress_callback:
                    progress_callback(f"Saving {student_number} to database...")

                update_success = self._repository.update_student(student_number, data)
                if update_success:
                    return True, "Student updated successfully"
                else:
                    return False, "CMS update succeeded but database update failed"
            else:
                logger.error(f"CMS update failed for student {student_number}")
                return (
                    False,
                    "CMS update failed - response did not contain 'Successful'",
                )

        except Exception as e:
            logger.error(f"Error pushing student {student_number}: {str(e)}")
            return False, f"Error: {str(e)}"

    def push_module(
        self,
        std_module_id: int,
        data: dict,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, str]:
        url = f"{BASE_URL}/r_stdmoduleedit.php?StdModuleID={std_module_id}"

        try:
            if progress_callback:
                progress_callback(f"Fetching edit form for module {std_module_id}...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#fr_stdmoduleedit")

            if not form:
                logger.error(f"Could not find edit form for module {std_module_id}")
                return False, "Could not find edit form"

            if progress_callback:
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

            if progress_callback:
                progress_callback(f"Pushing module {std_module_id} to CMS...")

            logger.info(f"Posting update for module {std_module_id}")
            post_response = self._browser.post(url, form_data)

            if "Successful" in post_response.text:
                logger.info(f"Successfully posted module {std_module_id} to CMS")

                if progress_callback:
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
                logger.error(f"CMS update failed for module {std_module_id}")
                return (
                    False,
                    "CMS update failed - response did not contain 'Successful'",
                )

        except Exception as e:
            logger.error(f"Error pushing module {std_module_id}: {str(e)}")
            return False, f"Error: {str(e)}"

    def push_semester(
        self,
        data: dict,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, str]:
        student_program_id = data.get("student_program_id")
        if not student_program_id:
            return False, "Missing student_program_id"

        url = f"{BASE_URL}/r_stdsemesteradd.php?StdProgramID={student_program_id}"

        try:
            if progress_callback:
                progress_callback(f"Fetching add form for semester...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#fr_stdsemesteradd")

            if not form:
                logger.error(f"Could not find add form for semester")
                return False, "Could not find add form"

            if progress_callback:
                progress_callback(f"Preparing semester data...")

            form_data = get_form_payload(form)

            form_data["a_add"] = "A"

            program_details = self._repository.get_student_program_details_by_id(
                student_program_id
            )

            if program_details:
                if program_details.get("std_no"):
                    form_data["x_StdProgramID"] = str(student_program_id)

                if program_details.get("school_id"):
                    form_data["x_SchoolID"] = str(program_details["school_id"])

                if program_details.get("program_id"):
                    form_data["x_ProgramID"] = str(program_details["program_id"])

                if program_details.get("structure_id"):
                    form_data["x_StructureID"] = str(program_details["structure_id"])

            form_data["x_CampusCode"] = "Lesotho"

            if "term" in data and data["term"]:
                form_data["x_TermCode"] = data["term"]

            if "structure_semester_id" in data and data["structure_semester_id"]:
                form_data["x_SemesterID"] = str(data["structure_semester_id"])

            if "status" in data and data["status"]:
                form_data["x_SemesterStatus"] = data["status"]

            if "caf_date" in data and data["caf_date"]:
                form_data["x_StdSemCAFDate"] = data["caf_date"]
            else:
                form_data["x_StdSemCAFDate"] = today()

            if progress_callback:
                progress_callback(f"Pushing semester to CMS...")

            logger.info(f"Posting new semester for program {student_program_id}")
            post_response = self._browser.post(url, form_data)

            if "Successful" in post_response.text:
                logger.info(
                    f"Successfully posted semester for program {student_program_id} to CMS"
                )

                if progress_callback:
                    progress_callback(f"Fetching created semester ID from CMS...")

                semester_ids = extract_student_semester_ids(str(student_program_id))

                matching_semester_id = None
                for sem_id in semester_ids:
                    sem_data = scrape_student_semester_data(sem_id)
                    if sem_data.get("term") == data.get("term"):
                        matching_semester_id = sem_id
                        break

                if not matching_semester_id:
                    logger.error(
                        f"Could not find created semester ID for term {data.get('term')}"
                    )
                    return (
                        False,
                        f"CMS update succeeded but could not retrieve created semester ID",
                    )

                if progress_callback:
                    progress_callback(f"Saving semester to database...")

                db_data = {
                    "id": matching_semester_id,
                    "term": data.get("term"),
                    "status": data.get("status"),
                    "caf_date": data.get("caf_date"),
                }

                if "semester_number" in data and data["semester_number"]:
                    db_data["semester_number"] = data["semester_number"]

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
            else:
                logger.error(f"CMS update failed for semester")
                return (
                    False,
                    "CMS update failed - response did not contain 'Successful'",
                )

        except Exception as e:
            logger.error(f"Error pushing semester: {str(e)}")
            return False, f"Error: {str(e)}"

    def update_semester(
        self,
        data: dict,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, str]:
        student_semester_id = data.get("student_semester_id")
        if not student_semester_id:
            return False, "Missing student_semester_id"

        url = f"{BASE_URL}/r_stdsemesteredit.php?StdSemesterID={student_semester_id}"

        try:
            if progress_callback:
                progress_callback(f"Fetching edit form for semester...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#fr_stdsemesteredit")

            if not form:
                logger.error(
                    f"Could not find edit form for semester {student_semester_id}"
                )
                return False, "Could not find edit form"

            if progress_callback:
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

            if progress_callback:
                progress_callback(f"Pushing semester update to CMS (step 1)...")

            logger.info(
                f"Posting update for semester {student_semester_id} (without term)"
            )
            form_data["x_TermCode"] = ""
            post_response = self._browser.post(url, form_data)

            if "Successful" not in post_response.text:
                logger.error(f"CMS update failed for semester {student_semester_id}")
                return (
                    False,
                    "CMS update failed - response did not contain 'Successful'",
                )

            if progress_callback:
                progress_callback(f"Fetching edit form again for semester...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#fr_stdsemesteredit")

            if not form:
                logger.error(f"Could not find edit form for second update")
                return False, "Could not find edit form for second update"

            if progress_callback:
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

            if progress_callback:
                progress_callback(f"Pushing semester update to CMS (step 2)...")

            logger.info(
                f"Posting update for semester {student_semester_id} (with term)"
            )
            post_response = self._browser.post(url, form_data)

            if "Successful" in post_response.text:
                logger.info(
                    f"Successfully posted semester {student_semester_id} to CMS"
                )

                if progress_callback:
                    progress_callback(f"Saving semester to database...")

                db_data = {
                    "id": student_semester_id,
                    "status": data.get("status"),
                }

                if "semester_number" in data and data["semester_number"]:
                    db_data["semester_number"] = data["semester_number"]

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
            else:
                logger.error(f"CMS update failed for semester {student_semester_id}")
                return (
                    False,
                    "CMS update failed - response did not contain 'Successful'",
                )

        except Exception as e:
            logger.error(f"Error updating semester: {str(e)}")
            return False, f"Error: {str(e)}"

    def push_student_module(
        self,
        student_semester_id: int,
        semester_module_id: int,
        module_status: str,
        module_code: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, str]:
        try:
            if progress_callback:
                progress_callback(f"Fetching add module form...")

            self._browser.fetch(
                f"{BASE_URL}/r_stdmodulelist.php?showmaster=1&StdSemesterID={student_semester_id}"
            )

            if progress_callback:
                progress_callback(f"Navigating to module add page...")

            add_response = self._browser.fetch(f"{BASE_URL}/r_stdmoduleadd1.php")
            page = BeautifulSoup(add_response.text, "lxml")

            form_data = get_form_payload(page)

            if progress_callback:
                progress_callback(f"Fetching module details...")

            credits = self._repository.get_semester_module_credits(semester_module_id)

            if credits is None:
                return False, "Semester module not found in database"

            module_string = f"{semester_module_id}-{module_status}-{credits}-1200"

            form_data["Submit"] = "Add+Modules"
            form_data["take[]"] = [module_string]

            if progress_callback:
                progress_callback(f"Pushing module to CMS...")

            logger.info(
                f"Posting module {semester_module_id} to semester {student_semester_id}"
            )
            self._browser.post(f"{BASE_URL}/r_stdmoduleadd1.php", form_data)

            if progress_callback:
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

            if progress_callback:
                progress_callback(f"Syncing new module to database...")

            from .scraper import scrape_student_modules_concurrent

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
            logger.error(f"Error pushing student module: {str(e)}")
            return False, f"Error: {str(e)}"
