from __future__ import annotations

import datetime
from typing import Callable, Optional

from base import get_logger
from base.browser import Browser
from features.enrollments.semester import SemesterEnrollmentService

from .repository import EnrollmentRequestRepository
from .scraper import get_cms_semester_modules, get_cms_semesters

logger = get_logger(__name__)


def today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


class EnrollmentService:
    def __init__(
        self, repository: Optional[EnrollmentRequestRepository] = None
    ) -> None:
        self._repository = repository or EnrollmentRequestRepository()
        self._browser = Browser()
        self._semester_service = SemesterEnrollmentService()

    def enroll_students(
        self,
        registration_request_ids: list[int],
        progress_callback: Callable[[str, int, int], None],
    ) -> tuple[int, int]:

        success_count = 0
        failed_count = 0

        for idx, request_id in enumerate(registration_request_ids):
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
        progress_callback: Callable[[str, int, int], None],
    ) -> bool:
        progress_callback(f"Fetching enrollment data...", 0, 100)

        enrollment_data = self._repository.get_enrollment_data(request_id)
        if not enrollment_data:
            logger.error(f"Registration request {request_id} not found")
            return False

        std_no = enrollment_data["std_no"]
        term_code = enrollment_data["term_code"]
        semester_number = enrollment_data["semester_number"]
        semester_status = enrollment_data["semester_status"]
        student_program_id = enrollment_data["student_program_id"]
        structure_id = enrollment_data["structure_id"]
        requested_modules = enrollment_data["modules"]

        if not student_program_id or not structure_id:
            logger.error(f"No active student program found for student {std_no}")
            return False

        logger.info(
            f"Enrolling student {std_no} for term {term_code}, semester {semester_number}"
        )
        logger.info(
            f"Found student program {student_program_id} with structure {structure_id}"
        )

        requested_module_codes = [mod.module_code for mod in requested_modules]
        logger.info(f"Requested modules for enrollment: {requested_module_codes}")

        progress_callback(
            f"Checking CMS for existing semesters for student {std_no}...", 20, 100
        )

        existing_semesters = get_cms_semesters(student_program_id)

        existing_semester_id = None
        for sem in existing_semesters:
            if sem.get("term") == term_code:
                existing_semester_id = sem.get("id")
                logger.info(
                    f"Found existing semester {existing_semester_id} for term {term_code} on CMS"
                )
                break

        if existing_semester_id:
            student_semester_id = existing_semester_id
            logger.info(f"Reusing existing semester {student_semester_id}")

            progress_callback(
                f"Reusing existing semester for student {std_no}...", 40, 100
            )
        else:
            logger.info(f"Creating new semester for student {std_no}, term {term_code}")

            progress_callback(
                f"Getting structure semester for student {std_no}...", 30, 100
            )

            normalized_semester_number = str(semester_number).strip().zfill(2)
            structure_semester_id = self._repository.get_structure_semester_by_number(
                structure_id, normalized_semester_number
            )
            if not structure_semester_id:
                logger.error(
                    f"Structure semester not found for structure {structure_id}, semester {semester_number}"
                )
                return False

            progress_callback(
                f"Creating semester on CMS for student {std_no}...", 35, 100
            )

            created_sem_id = self._semester_service.create_semester_on_cms(
                student_program_id,
                structure_id,
                term_code,
                structure_semester_id,
                semester_status,
                today(),
            )

            if not created_sem_id:
                logger.error(f"Failed to create semester on CMS for student {std_no}")
                return False

            student_semester_id = created_sem_id
            logger.info(f"Created new semester {student_semester_id} on CMS")

            progress_callback(
                f"Saving semester to database for student {std_no}...", 40, 100
            )

            self._repository.upsert_student_semester(
                student_program_id,
                {
                    "id": student_semester_id,
                    "term": term_code,
                    "structure_semester_id": structure_semester_id,
                    "status": semester_status,
                    "caf_date": today(),
                    "registration_request_id": request_id,
                },
            )

        progress_callback(f"Checking existing modules for student {std_no}...", 50, 100)

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
            progress_callback(
                f"Pushing {len(modules_to_push)} modules to CMS in batch...",
                60,
                100,
            )

            logger.info(
                f"Pushing {len(modules_to_push)} modules to semester {student_semester_id} "
                f"({modules_skipped} already exist)"
            )

            self._semester_service.add_modules_batch(
                student_semester_id, modules_to_push
            )

            progress_callback(
                f"Syncing {len(modules_to_push)} modules to database...",
                80,
                100,
            )

            updated_modules = get_cms_semester_modules(student_semester_id)
            updated_modules_map = {mod["module_code"]: mod for mod in updated_modules}

            modules_added = 0
            modules_failed = []

            for req_mod in requested_modules:
                module_code = req_mod.module_code

                if module_code in existing_module_codes:
                    continue

                if module_code in updated_modules_map:
                    cms_mod = updated_modules_map[module_code]
                    self._repository.upsert_student_module(
                        {
                            "id": cms_mod["id"],
                            "semester_module_id": req_mod.semester_module_id,
                            "status": req_mod.module_status,
                            "credits": req_mod.credits or 0,
                            "marks": "NM",
                            "grade": "NM",
                            "student_semester_id": student_semester_id,
                        }
                    )
                    modules_added += 1
                    logger.info(f"Successfully saved module {module_code} to database")
                else:
                    modules_failed.append(module_code)
                    logger.error(
                        f"Module {module_code} not found on CMS after push. "
                        f"Available modules: {list(updated_modules_map.keys())}"
                    )

            failed_count = len(modules_failed)

            if modules_failed:
                logger.warning(
                    f"Failed to sync {failed_count} modules to database: {modules_failed}"
                )

            logger.info(
                f"Enrollment complete for request {request_id}: "
                f"{modules_added} modules added, {modules_skipped} skipped, {failed_count} failed"
            )
        else:
            modules_added = 0
            failed_count = 0
            logger.info(
                f"All {modules_skipped} modules already exist on website for request {request_id}"
            )

        progress_callback(f"Finalizing enrollment for student {std_no}...", 95, 100)

        if failed_count == 0:
            self._repository.update_registration_request_status(
                request_id, "registered"
            )
            logger.info(f"Marked registration request {request_id} as registered")

            progress_callback(f"Enrollment complete for student {std_no}", 100, 100)
            return True
        else:
            logger.warning(
                f"Request {request_id} partially completed with {failed_count} failures"
            )
            return False

    def check_clearances_for_requests(self, request_ids: list[int]) -> str:
        issues = []
        for request_id in request_ids:
            clearances = self._repository.get_clearances_for_request(request_id)
            if not clearances:
                issues.append(f"Request #{request_id}: No clearances found")
                continue

            pending_departments = []
            rejected_departments = []

            for clearance in clearances:
                if clearance.status == "pending":
                    pending_departments.append(clearance.department)
                elif clearance.status == "rejected":
                    rejected_departments.append(clearance.department)

            if pending_departments or rejected_departments:
                issue_parts = []
                if pending_departments:
                    issue_parts.append(f"Pending: {', '.join(pending_departments)}")
                if rejected_departments:
                    issue_parts.append(f"Rejected: {', '.join(rejected_departments)}")
                issues.append(f"Request #{request_id}: {', '.join(issue_parts)}")

        return "\n".join(issues)
