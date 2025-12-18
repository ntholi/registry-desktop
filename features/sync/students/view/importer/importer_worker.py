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
                    std_no, progress_callback, self.project.import_options
                )

                if was_updated:
                    self.project.success_count += 1
                else:
                    self.project.failed_count += 1
                    if self.project.failed_students is not None:
                        self.project.failed_students.append(std_no)

                ImporterProjectManager.save_project(self.project)

                student_started = False

            except Exception as e:
                logger.error(
                    f"Error importing student {std_no}: {str(e)}",
                )
                self.callback("error", f"Error importing student {std_no}: {str(e)}")
                self.project.failed_count += 1
                if self.project.failed_students is not None:
                    self.project.failed_students.append(std_no)
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
