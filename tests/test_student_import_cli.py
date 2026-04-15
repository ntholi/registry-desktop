import queue
import threading
import unittest
from dataclasses import dataclass, field
from unittest.mock import Mock

from features.sync.students.import_cli import (
    ImportCliOptions,
    StudentImportCli,
    TerminalConsole,
    build_import_options,
    has_selected_import_data,
    validate_student_range,
)
from features.sync.students.importer_project import ImporterProject


class FakeConsole(TerminalConsole):
    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or []
        self.messages: list[str] = []
        super().__init__(input_func=self._read_input)

    def _read_input(self, prompt: str) -> str:
        self.messages.append(prompt)
        if not self.responses:
            raise AssertionError("No console responses left")
        return self.responses.pop(0)

    def print(self, message: str = "") -> None:
        self.messages.append(message)


@dataclass
class FakeProjectManager:
    project: ImporterProject | None = None
    saved_projects: list[ImporterProject] = field(default_factory=list)
    deleted: bool = False
    created_args: tuple[str, str, dict[str, bool]] | None = None

    def load_project(self) -> ImporterProject | None:
        return self.project

    def save_project(self, project: ImporterProject) -> None:
        self.project = project
        self.saved_projects.append(project)

    def delete_project(self) -> None:
        self.deleted = True
        self.project = None

    def create_project(
        self, start_student: str, end_student: str, import_options: dict[str, bool]
    ) -> ImporterProject:
        self.created_args = (start_student, end_student, import_options)
        self.project = ImporterProject(
            start_student=start_student,
            end_student=end_student,
            current_student=start_student,
            import_options=import_options,
            status="pending",
        )
        return self.project

    def count_students(self, start: str, end: str) -> int:
        return int(end) - int(start) + 1

    def count_remaining_students(self, project: ImporterProject) -> int:
        return int(project.end_student) - int(project.current_student) + 1


class StudentImportCliTests(unittest.TestCase):
    def make_options(self, **overrides) -> ImportCliOptions:
        values = {
            "country": None,
            "start": None,
            "end": None,
            "auto_detect": False,
            "resume": False,
            "status_only": False,
            "student_info": True,
            "personal_info": True,
            "education_history": True,
            "enrollment_data": True,
            "addresses": True,
            "skip_active_term": False,
            "delete_programs_before_import": False,
        }
        values.update(overrides)
        return ImportCliOptions(**values)

    def test_validate_student_range_rejects_large_ranges(self):
        with self.assertRaises(ValueError):
            validate_student_range("901000001", "901020002")

    def test_build_import_options_tracks_selected_sections(self):
        options = self.make_options(personal_info=False, addresses=False)
        import_options = build_import_options(options)

        self.assertFalse(import_options["personal_info"])
        self.assertFalse(import_options["addresses"])
        self.assertTrue(has_selected_import_data(import_options))

    def test_load_or_create_project_marks_running_project_as_paused(self):
        project = ImporterProject(
            start_student="901000001",
            end_student="901000003",
            current_student="901000002",
            import_options={"student_info": True},
            status="running",
        )
        manager = FakeProjectManager(project=project)
        console = FakeConsole()
        cli = StudentImportCli(
            console=console,
            sync_service=Mock(),
            project_manager=manager,
            range_detector=lambda: ("901000001", "901000003", 3),
        )

        loaded_project, should_start = cli._load_or_create_project(self.make_options())

        self.assertIs(loaded_project, project)
        self.assertFalse(should_start)
        self.assertEqual(project.status, "paused")
        self.assertTrue(manager.saved_projects)

    def test_load_or_create_project_creates_new_project_when_none_exists(self):
        manager = FakeProjectManager()
        console = FakeConsole()
        cli = StudentImportCli(
            console=console,
            sync_service=Mock(),
            project_manager=manager,
            range_detector=lambda: ("901000001", "901000003", 3),
        )

        project, should_start = cli._load_or_create_project(
            self.make_options(start="901000001", end="901000003")
        )

        self.assertIsNotNone(project)
        self.assertTrue(should_start)
        self.assertIsNotNone(manager.created_args)

    def test_handle_missing_sponsor_exit_sets_exit_requested(self):
        manager = FakeProjectManager()
        console = FakeConsole(["3"])
        cli = StudentImportCli(
            console=console,
            sync_service=Mock(),
            project_manager=manager,
            range_detector=lambda: ("901000001", "901000003", 3),
        )
        response_holder = {"create": False}
        response_event = threading.Event()

        result = cli._handle_event(
            "missing_sponsor",
            ("ABC", "SEM1", "2026", response_holder, response_event),
        )

        self.assertIsNone(result)
        self.assertFalse(response_holder["create"])
        self.assertTrue(response_event.is_set())
        self.assertTrue(cli.exit_requested)

    def test_handle_finished_deletes_project(self):
        project = ImporterProject(
            start_student="901000001",
            end_student="901000003",
            current_student="901000003",
            import_options={"student_info": True},
            status="completed",
            success_count=3,
        )
        manager = FakeProjectManager(project=project)
        console = FakeConsole()
        cli = StudentImportCli(
            console=console,
            sync_service=Mock(),
            project_manager=manager,
            range_detector=lambda: ("901000001", "901000003", 3),
        )

        result = cli._handle_event("finished", (project,))

        self.assertEqual(result, "completed")
        self.assertTrue(manager.deleted)
        self.assertIsNone(cli.project)

    def test_handle_stopped_returns_exit_when_requested(self):
        project = ImporterProject(
            start_student="901000001",
            end_student="901000003",
            current_student="901000002",
            import_options={"student_info": True},
            status="paused",
        )
        manager = FakeProjectManager(project=project)
        console = FakeConsole()
        cli = StudentImportCli(
            console=console,
            sync_service=Mock(),
            project_manager=manager,
            range_detector=lambda: ("901000001", "901000003", 3),
        )
        cli.exit_requested = True

        result = cli._handle_event("stopped", (project,))

        self.assertEqual(result, "exit")

    def test_retry_next_failed_student_processes_retry_events(self):
        project = ImporterProject(
            start_student="901000001",
            end_student="901000003",
            current_student="901000002",
            import_options={"student_info": True},
            status="paused",
            failed_students=["901000001"],
        )
        manager = FakeProjectManager(project=project)
        console = FakeConsole()
        class RetryCli(StudentImportCli):
            def _start_retry_worker(self, student_number: str) -> None:
                self.retry_worker = Mock()

        cli = RetryCli(
            console=console,
            sync_service=Mock(),
            project_manager=manager,
            range_detector=lambda: ("901000001", "901000003", 3),
        )
        cli.project = project
        cli.event_queue = queue.Queue()
        cli.event_queue.put(("retry_finished", (project, "901000001", True, "")))

        result = cli._retry_next_failed_student()

        self.assertIsNone(result)

    def test_ctrl_c_requests_safe_pause_and_exit(self):
        project = ImporterProject(
            start_student="901000001",
            end_student="901000003",
            current_student="901000002",
            import_options={"student_info": True},
            status="running",
        )
        manager = FakeProjectManager(project=project)
        console = FakeConsole()
        cli = StudentImportCli(
            console=console,
            sync_service=Mock(),
            project_manager=manager,
            range_detector=lambda: ("901000001", "901000003", 3),
        )
        cli.project = project
        worker = Mock()
        worker.is_alive.return_value = True
        cli.worker = worker

        class InterruptQueue(queue.Queue[tuple[str, tuple[object, ...]]]):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def get(
                self, block: bool = True, timeout: float | None = None
            ) -> tuple[str, tuple[object, ...]]:
                self.calls += 1
                if self.calls == 1:
                    raise KeyboardInterrupt()
                return ("stopped", (project,))

        cli.event_queue = InterruptQueue()

        result = cli._run_worker_loop()

        self.assertEqual(result, "exit")
        self.assertTrue(cli.exit_requested)
        worker.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
