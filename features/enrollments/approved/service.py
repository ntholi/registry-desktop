from __future__ import annotations

from typing import Callable, Optional

from base import get_logger

from .repository import ApprovedEnrollmentRepository

logger = get_logger(__name__)


class EnrollmentService:
    def __init__(
        self, repository: Optional[ApprovedEnrollmentRepository] = None
    ) -> None:
        self._repository = repository or ApprovedEnrollmentRepository()

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

                logger.info(
                    f"TODO: Implement enrollment logic for request {request_id}"
                )

                success_count += 1

            except Exception as e:
                logger.error(f"Error enrolling request {request_id}: {str(e)}")
                failed_count += 1

        return success_count, failed_count
