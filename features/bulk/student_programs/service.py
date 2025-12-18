from __future__ import annotations

from typing import Callable, Optional

from bs4 import BeautifulSoup, Tag

from base import get_logger
from base.browser import BASE_URL, Browser, get_form_payload
from features.common.cms_utils import post_cms_form

from .repository import BulkStudentProgramsRepository, StudentProgramRow

logger = get_logger(__name__)


class StudentProgramService:
    def __init__(
        self, repository: Optional[BulkStudentProgramsRepository] = None
    ) -> None:
        self._repository = repository or BulkStudentProgramsRepository()
        self._browser = Browser()

    def update_student_program_structure(
        self,
        student_program: StudentProgramRow,
        new_structure_id: int,
        new_structure_code: str,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        cms_program_id = self._repository.get_cms_student_program_id(
            student_program.student_program_id
        )

        if not cms_program_id:
            return False, "Could not find CMS program ID"

        url = f"{BASE_URL}/r_stdprogramedit.php?StdProgramID={cms_program_id}"

        try:
            progress_callback(f"Fetching edit form for {student_program.std_no}...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#fr_stdprogramedit")

            if not form:
                logger.error(
                    f"Could not find edit form - std_no={student_program.std_no}, "
                    f"cms_program_id={cms_program_id}, url={url}, "
                    f"response_length={len(response.text) if response and response.text else 0}"
                )
                return False, "Could not find edit form"

            progress_callback(f"Preparing data for {student_program.std_no}...")

            form_data = get_form_payload(form)

            form_data["a_edit"] = "U"

            form_data["x_StructureID"] = str(new_structure_id)

            self._populate_form_with_current_data(
                form, form_data, student_program, page
            )

            progress_callback(
                f"Pushing structure update for {student_program.std_no} to CMS..."
            )

            cms_success, cms_message = post_cms_form(self._browser, url, form_data)

            if cms_success:
                progress_callback(f"Saving {student_program.std_no} to database...")

                db_success, db_message = (
                    self._repository.update_student_program_structure(
                        student_program.student_program_id, new_structure_id
                    )
                )

                if db_success:
                    return True, "Structure updated successfully"
                else:
                    return (
                        False,
                        f"CMS update succeeded but database update failed: {db_message}",
                    )
            else:
                return False, cms_message

        except Exception as e:
            logger.error(
                f"Error updating student program structure - "
                f"std_no={student_program.std_no}, "
                f"cms_program_id={cms_program_id}, "
                f"new_structure_id={new_structure_id}, "
                f"error={str(e)}"
            )
            return False, f"Error: {str(e)}"

    def _populate_form_with_current_data(
        self,
        form: Tag,
        form_data: dict,
        student_program: StudentProgramRow,
        page: BeautifulSoup,
    ):
        form_data["x_StudentID"] = student_program.std_no

        if student_program.reg_date:
            form_data["x_StdProgRegDate"] = student_program.reg_date

        if student_program.start_term:
            form_data["x_TermCode"] = student_program.start_term

        if student_program.intake_date:
            form_data["x_ProgramIntakeDate"] = student_program.intake_date

        stream_select = form.select_one("select#x_ProgStreamCode")
        if stream_select:
            selected_option = stream_select.select_one("option[selected]")
            if selected_option:
                form_data["x_ProgStreamCode"] = selected_option.get("value", "")
            elif student_program.stream:
                form_data["x_ProgStreamCode"] = student_program.stream
            else:
                form_data["x_ProgStreamCode"] = "Normal"
        elif student_program.stream:
            form_data["x_ProgStreamCode"] = student_program.stream

        status_select = form.select_one("select#x_ProgramStatus")
        if status_select:
            selected_option = status_select.select_one("option[selected]")
            if selected_option:
                form_data["x_ProgramStatus"] = selected_option.get("value", "")
            elif student_program.status:
                form_data["x_ProgramStatus"] = student_program.status
        elif student_program.status:
            form_data["x_ProgramStatus"] = student_program.status

        self._preserve_select_values(
            form,
            form_data,
            [
                "x_TransferFrom",
                "x_AssistProviderCode",
                "x_AssistSchCode",
                "x_GradingVersion",
            ],
        )

        self._preserve_text_values(
            form,
            form_data,
            [
                "x_StdProgRemark",
                "x_AssistMemo",
                "x_AssistStdAcc",
                "x_AssistPercent",
                "x_AssistAmount",
                "x_AssistNetAmount",
                "x_AssistBond",
                "x_AssistApprovalDate",
                "x_AssistDate",
                "x_AssistExpiryDate",
                "x_AssistRemark",
                "x_LOASubmittedDate",
                "x_GraduationDate",
                "x_CertSN",
                "x_CertPrintDate",
                "x_CertCollDate",
                "x_GradSession",
                "x_GradGuest",
                "x_GradGownSize",
                "x_GradGownPickUp",
                "x_GradGownReturn",
                "x_FdnCertSN",
                "x_FdnCertPrintDate",
                "x_FdnCertCollDate",
                "x_CurtinID",
            ],
        )

        self._preserve_checkbox_values(
            form,
            form_data,
            [
                "x_LOASubmitted",
                "x_DualProgram",
                "x_GradRSVP",
            ],
        )

        if student_program.graduation_date:
            form_data["x_GraduationDate"] = student_program.graduation_date

    def _preserve_select_values(
        self, form: Tag, form_data: dict, field_names: list[str]
    ):
        for field_name in field_names:
            select = form.select_one(f"select#{field_name}")
            if select:
                selected_option = select.select_one("option[selected]")
                if selected_option:
                    form_data[field_name] = selected_option.get("value", "")
                else:
                    first_option = select.select_one("option")
                    if first_option:
                        form_data[field_name] = first_option.get("value", "")

    def _preserve_text_values(self, form: Tag, form_data: dict, field_names: list[str]):
        for field_name in field_names:
            text_input = form.select_one(f"input#{field_name}")
            if text_input:
                value = text_input.get("value", "")
                if value:
                    form_data[field_name] = value
            else:
                textarea = form.select_one(f"textarea#{field_name}")
                if textarea:
                    value = textarea.get_text(strip=True)
                    if value:
                        form_data[field_name] = value

    def _preserve_checkbox_values(
        self, form: Tag, form_data: dict, field_names: list[str]
    ):
        for field_name in field_names:
            checkbox = form.select_one(f"input[name='{field_name}']")
            if checkbox:
                if checkbox.has_attr("checked"):
                    form_data[field_name] = checkbox.get("value", "Y")
