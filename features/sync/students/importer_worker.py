import threading
from typing import Callable

from base import get_logger

from .importer_project import ImporterProject, ImporterProjectManager
from .service import SponsorResolutionError

logger = get_logger(__name__)


class ImporterWorker(threading.Thread):
    def __init__(self, project: ImporterProject, sync_service, callback: Callable):
        super().__init__(daemon=True)
        self.project = project
        self.sync_service = sync_service
        self.callback = callback
        self._stop_flag = threading.Event()

    def stop(self):
        self._stop_flag.set()
        logger.info("Importer worker received stop signal")

    def is_stopped(self) -> bool:
        return self._stop_flag.is_set()

    def _request_missing_sponsor(
        self, sponsor_code: str, semester_id: str, term: str | None
    ) -> bool:
        response_holder = {"create": False}
        response_event = threading.Event()
        self.callback(
            "missing_sponsor",
            sponsor_code,
            semester_id,
            term,
            response_holder,
            response_event,
        )
        response_event.wait()
        return bool(response_holder["create"])

    def run(self):
        logger.info(
            f"Importer worker starting for range {self.project.start_student} to {self.project.end_student}"
        )

        self.project.status = "running"
        ImporterProjectManager.save_project(self.project)

        remaining_students = ImporterProjectManager.get_remaining_students(self.project)
        total_students = len(
            ImporterProjectManager.generate_student_numbers(
                self.project.start_student, self.project.end_student
            )
        )

        for idx, std_no in enumerate(remaining_students):
            if self.is_stopped():
                logger.info(
                    f"Importer worker stopped before starting student {std_no}, "
                    f"processed {idx} students"
                )
                self.project.status = "paused"
                ImporterProjectManager.save_project(self.project)
                self.callback("stopped", self.project)
                return

            self.project.current_student = std_no
            ImporterProjectManager.save_project(self.project)

            current_overall = total_students - len(remaining_students) + idx + 1

            student_started = True

            try:

                def progress_callback(message, current, total):
                    overall_progress = (current_overall - 1) * 3 + current
                    overall_total = total_students * 3
                    self.callback(
                        "progress",
                        message,
                        overall_progress,
                        overall_total,
                        self.project,
                    )

                was_updated = self.sync_service.fetch_student(
                    std_no,
                    progress_callback,
                    self.project.import_options,
                    self._request_missing_sponsor,
                )

                if was_updated:
                    self.project.success_count += 1
                else:
                    ImporterProjectManager.add_failed_student(self.project, std_no)

                ImporterProjectManager.save_project(self.project)

                student_started = False

            except SponsorResolutionError as e:
                logger.warning(
                    f"Import stopped while syncing student {std_no}: {str(e)}"
                )
                ImporterProjectManager.add_failed_student(self.project, std_no)
                self.project.status = "paused"
                ImporterProjectManager.save_project(self.project)
                self.callback("cancelled", self.project, str(e))
                return
            except Exception as e:
                logger.error(
                    f"Error importing student {std_no}: {str(e)}",
                )
                self.callback("error", f"Error importing student {std_no}: {str(e)}")
                ImporterProjectManager.add_failed_student(self.project, std_no)
                ImporterProjectManager.save_project(self.project)

                student_started = False

            if self.is_stopped():
                if student_started:
                    logger.info(
                        f"Importer worker stopped after completing student {std_no}. "
                        f"This student will be re-imported on resume."
                    )
                else:
                    next_index = idx + 1
                    if next_index < len(remaining_students):
                        self.project.current_student = remaining_students[next_index]
                        logger.info(
                            f"Importer worker stopped. Next student to import: "
                            f"{remaining_students[next_index]}"
                        )
                    else:
                        logger.info(
                            f"Importer worker stopped after completing student {std_no}"
                        )

                self.project.status = "paused"
                ImporterProjectManager.save_project(self.project)
                self.callback("stopped", self.project)
                return

        if not self.is_stopped():
            self.project.status = "completed"
            ImporterProjectManager.save_project(self.project)
            logger.info(
                f"Importer worker completed. Success: {self.project.success_count}, "
                f"Failed: {self.project.failed_count}"
            )
            self.callback("finished", self.project)


class ImporterRetryWorker(threading.Thread):
    def __init__(
        self,
        project: ImporterProject,
        student_number: str,
        sync_service,
        callback: Callable,
    ):
        super().__init__(daemon=True)
        self.project = project
        self.student_number = student_number
        self.sync_service = sync_service
        self.callback = callback

    def _request_missing_sponsor(
        self, sponsor_code: str, semester_id: str, term: str | None
    ) -> bool:
        response_holder = {"create": False}
        response_event = threading.Event()
        self.callback(
            "missing_sponsor",
            sponsor_code,
            semester_id,
            term,
            response_holder,
            response_event,
        )
        response_event.wait()
        return bool(response_holder["create"])

    def run(self):
        logger.info(f"Retry worker starting for student {self.student_number}")

        try:

            def progress_callback(message, current, total):
                self.callback(
                    "retry_progress",
                    message,
                    current,
                    total,
                    self.student_number,
                    self.project,
                )

            was_updated = self.sync_service.fetch_student(
                self.student_number,
                progress_callback,
                self.project.import_options,
                self._request_missing_sponsor,
            )

            if was_updated:
                if not ImporterProjectManager.resolve_failed_student(
                    self.project, self.student_number
                ):
                    self.project.success_count += 1
                ImporterProjectManager.save_project(self.project)
                self.callback(
                    "retry_finished",
                    self.project,
                    self.student_number,
                    True,
                    "",
                )
                return

            ImporterProjectManager.add_failed_student(self.project, self.student_number)
            ImporterProjectManager.save_project(self.project)
            self.callback(
                "retry_finished",
                self.project,
                self.student_number,
                False,
                f"Retry did not import student {self.student_number}.",
            )
        except SponsorResolutionError as e:
            logger.warning(
                f"Retry stopped while syncing student {self.student_number}: {str(e)}"
            )
            ImporterProjectManager.add_failed_student(self.project, self.student_number)
            ImporterProjectManager.save_project(self.project)
            self.callback(
                "retry_finished",
                self.project,
                self.student_number,
                False,
                str(e),
            )
        except Exception as e:
            error_msg = f"Error importing student {self.student_number}: {str(e)}"
            logger.error(error_msg)
            ImporterProjectManager.add_failed_student(self.project, self.student_number)
            ImporterProjectManager.save_project(self.project)
            self.callback(
                "retry_finished",
                self.project,
                self.student_number,
                False,
                error_msg,
            )
