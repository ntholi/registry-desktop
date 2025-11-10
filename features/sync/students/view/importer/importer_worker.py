import threading
from typing import Callable

from base import get_logger

from .importer_project import ImporterProject, ImporterProjectManager

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
                    f"Importer worker stopped at student {std_no}, processed {idx} students"
                )
                self.callback("stopped", self.project)
                return

            self.project.current_student = std_no
            ImporterProjectManager.save_project(self.project)

            current_overall = (
                total_students - len(remaining_students) + idx + 1
            )

            try:

                def progress_callback(message, current, total):
                    if self.is_stopped():
                        return

                    overall_progress = (current_overall - 1) * 3 + current
                    overall_total = total_students * 3
                    self.callback(
                        "progress", message, overall_progress, overall_total, self.project
                    )

                if self.is_stopped():
                    logger.info(f"Importer worker stopped before fetching {std_no}")
                    self.callback("stopped", self.project)
                    return

                was_updated = self.sync_service.fetch_student(
                    std_no, progress_callback, self.project.import_options
                )

                if self.is_stopped():
                    logger.info(f"Importer worker stopped after fetching {std_no}")
                    self.callback("stopped", self.project)
                    return

                if was_updated:
                    self.project.success_count += 1
                else:
                    self.project.failed_count += 1
                    self.project.failed_students.append(std_no)

                ImporterProjectManager.save_project(self.project)

            except Exception as e:
                logger.error(
                    f"Error importing student {std_no}: {str(e)}",
                )
                self.callback("error", f"Error importing student {std_no}: {str(e)}")
                self.project.failed_count += 1
                self.project.failed_students.append(std_no)
                ImporterProjectManager.save_project(self.project)

                if self.is_stopped():
                    logger.info(f"Importer worker stopped after error on {std_no}")
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
