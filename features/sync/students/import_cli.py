from __future__ import annotations

import argparse
import queue
import sys
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence, TextIO, cast, runtime_checkable

from base.runtime_config import get_current_country_code, has_complete_runtime_configuration
from database.connection import configure_database_urls_for_country
from features.sync.students.scraper import detect_student_range

from .importer_project import ImporterProject, ImporterProjectManager
from .importer_worker import ImporterRetryWorker, ImporterWorker
from .service import StudentSyncService

MenuOption = tuple[str, str]
WorkerEvent = tuple[str, tuple[object, ...]]


@dataclass(frozen=True)
class ImportCliOptions:
    country: str | None
    start: str | None
    end: str | None
    auto_detect: bool
    resume: bool
    status_only: bool
    student_info: bool
    personal_info: bool
    education_history: bool
    enrollment_data: bool
    addresses: bool
    skip_active_term: bool
    delete_programs_before_import: bool


class ImportProjectStore(Protocol):
    def load_project(self) -> ImporterProject | None: ...

    def save_project(self, project: ImporterProject) -> None: ...

    def delete_project(self) -> None: ...

    def create_project(
        self, start_student: str, end_student: str, import_options: dict[str, bool]
    ) -> ImporterProject: ...

    def count_students(self, start: str, end: str) -> int: ...

    def count_remaining_students(self, project: ImporterProject) -> int: ...


@runtime_checkable
class SettableEvent(Protocol):
    def set(self) -> None: ...


class TerminalConsole:
    def __init__(
        self,
        input_func: Callable[[str], str] = input,
        output: TextIO | None = None,
    ):
        self._input = input_func
        self._output = output or sys.stdout

    def print(self, message: str = "") -> None:
        print(message, file=self._output)

    def prompt_text(self, label: str, default: str | None = None) -> str:
        suffix = f" [{default}]" if default else ""
        response = self._input(f"{label}{suffix}: ").strip()
        if response:
            return response
        return default or ""

    def choose(
        self,
        title: str,
        options: Sequence[MenuOption],
        default: str | None = None,
    ) -> str:
        self.print(title)
        for index, (_, label) in enumerate(options, start=1):
            self.print(f"{index}. {label}")

        default_index = ""
        if default is not None:
            for index, (key, _) in enumerate(options, start=1):
                if key == default:
                    default_index = str(index)
                    break

        valid_keys = {key.lower(): key for key, _ in options}
        while True:
            raw = self.prompt_text("Select an option", default_index).strip().lower()
            if raw.isdigit():
                option_index = int(raw) - 1
                if 0 <= option_index < len(options):
                    return options[option_index][0]
            if raw in valid_keys:
                return valid_keys[raw]
            self.print("Invalid selection.")


class StudentImportCli:
    def __init__(
        self,
        console: TerminalConsole | None = None,
        sync_service: StudentSyncService | None = None,
        project_manager: ImportProjectStore = ImporterProjectManager,
        range_detector: Callable[[], tuple[str, str, int]] = detect_student_range,
    ):
        self.console = console or TerminalConsole()
        self.sync_service = sync_service or StudentSyncService()
        self.project_manager = project_manager
        self.range_detector = range_detector
        self.project: ImporterProject | None = None
        self.worker: ImporterWorker | None = None
        self.retry_worker: ImporterRetryWorker | None = None
        self.event_queue: queue.Queue[WorkerEvent] = queue.Queue()
        self.exit_requested = False
        self.last_progress_signature: tuple[str, int, int, int, int] | None = None

    def run(self, options: ImportCliOptions) -> int:
        self._ensure_runtime_configuration(options.country)
        project, should_start = self._load_or_create_project(options)

        if project is None:
            self.console.print("No active import project was found.")
            return 0

        self.project = project

        if options.status_only:
            self._print_project_status()
            return 0

        if should_start:
            self._start_worker()

        while True:
            if self.project is None:
                return 0

            if self.project.status == "running":
                result = self._run_worker_loop()
                if result == "completed":
                    return 0
                if result == "exit":
                    return 0
                continue

            action = self._prompt_paused_action()
            if action == "resume":
                self._start_worker()
                continue
            if action == "retry":
                result = self._retry_next_failed_student()
                if result == "exit":
                    return 0
                continue
            if action == "status":
                self._print_project_status()
                continue
            if action == "failed":
                self._print_failed_students()
                continue
            if action == "exit":
                self.console.print("Leaving the import project paused and resumable.")
                return 0

    def on_worker_callback(self, event_type: str, *args: object) -> None:
        self.event_queue.put((event_type, args))

    def _ensure_runtime_configuration(self, country: str | None) -> None:
        if not has_complete_runtime_configuration():
            raise ValueError(
                "Saved runtime configuration is missing. Run main.py and save the country and database connection first."
            )

        selected_country = country or get_current_country_code()
        if not selected_country:
            raise ValueError("No runtime country has been selected.")

        configure_database_urls_for_country(selected_country)

    def _load_or_create_project(
        self, options: ImportCliOptions
    ) -> tuple[ImporterProject | None, bool]:
        existing_project = self.project_manager.load_project()
        if existing_project and existing_project.status in {"pending", "running", "paused"}:
            if options.start or options.end or options.auto_detect:
                raise ValueError(
                    "An active import project already exists. Resume that project instead of creating a new one."
                )
            if existing_project.status == "running":
                existing_project.status = "paused"
                self.project_manager.save_project(existing_project)
                self.console.print(
                    "The saved project was marked as running. It has been treated as paused so you can resume it safely from the CLI."
                )
            return existing_project, options.resume

        if options.status_only:
            return None, False

        if options.resume:
            raise ValueError("No active import project was found to resume.")

        created_project = self._create_project(options)
        self.console.print(
            f"Created import project for {created_project.start_student} to {created_project.end_student}."
        )
        return created_project, True

    def _create_project(self, options: ImportCliOptions) -> ImporterProject:
        if options.auto_detect:
            start_student, end_student, total_students = self.range_detector()
            self.console.print(
                f"Detected {total_students} students in CMS: {start_student} to {end_student}."
            )
        else:
            start_student = options.start or self.console.prompt_text(
                "First student number"
            )
            end_student = options.end or self.console.prompt_text("Last student number")

        start_student, end_student = validate_student_range(start_student, end_student)
        import_options = build_import_options(options)
        if not has_selected_import_data(import_options):
            raise ValueError("Select at least one data type to import.")
        return self.project_manager.create_project(
            start_student,
            end_student,
            import_options,
        )

    def _start_worker(self) -> None:
        if self.project is None:
            raise ValueError("Cannot start an import without a project.")

        if self.worker and self.worker.is_alive():
            return

        self.exit_requested = False
        self.project.status = "running"
        self.project_manager.save_project(self.project)
        self.worker = ImporterWorker(
            self.project,
            self.sync_service,
            self.on_worker_callback,
        )
        self.worker.start()
        self.console.print(
            f"Running import for {self.project.start_student} to {self.project.end_student}. Press Ctrl+C to pause safely after the current student and exit."
        )

    def _start_retry_worker(self, student_number: str) -> None:
        if self.project is None:
            raise ValueError("Cannot retry without an import project.")

        self.retry_worker = ImporterRetryWorker(
            self.project,
            student_number,
            self.sync_service,
            self.on_worker_callback,
        )
        self.retry_worker.start()
        self.console.print(f"Retrying failed student {student_number}.")

    def _run_worker_loop(self) -> str:
        while self.project is not None and self.project.status == "running":
            try:
                event_type, args = self.event_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            except KeyboardInterrupt:
                self._request_pause(exit_after_pause=True)
                continue

            result = self._handle_event(event_type, args)
            if result is not None:
                return result

        return "paused"

    def _retry_next_failed_student(self) -> str | None:
        if self.project is None or not self.project.failed_students:
            self.console.print("There are no failed students to retry.")
            return None

        student_number = self.project.failed_students[0]
        self._start_retry_worker(student_number)

        while self.retry_worker is not None:
            try:
                event_type, args = self.event_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            result = self._handle_event(event_type, args)
            if result == "exit":
                return "exit"
            if result == "retry_finished":
                return None

        return None

    def _handle_event(self, event_type: str, args: tuple[object, ...]) -> str | None:
        if event_type == "progress":
            message, current, total, project = args
            if not isinstance(message, str):
                raise ValueError("Invalid progress message.")
            if not isinstance(current, int) or not isinstance(total, int):
                raise ValueError("Invalid progress values.")
            if not isinstance(project, ImporterProject):
                raise ValueError("Invalid progress project.")
            self.project = project
            self._print_progress(message, current, total, project)
            return None

        if event_type == "missing_sponsor":
            sponsor_code, semester_id, term, response_holder, response_event = args
            if not isinstance(sponsor_code, str) or not isinstance(semester_id, str):
                raise ValueError("Invalid missing sponsor payload.")
            if not isinstance(response_holder, dict):
                raise ValueError("Invalid missing sponsor response holder.")
            if not isinstance(response_event, SettableEvent):
                raise ValueError("Invalid missing sponsor response event.")
            settable_event = cast(SettableEvent, response_event)
            action = self.console.choose(
                (
                    f"Sponsor '{sponsor_code}' is missing for semester {semester_id}"
                    f"{f' (term {term})' if isinstance(term, str) and term else ''}."
                ),
                [
                    ("create", "Create the sponsor and continue"),
                    ("pause", "Pause the import without creating the sponsor"),
                    ("exit", "Pause the import and exit the CLI"),
                ],
                default="create",
            )
            response_holder["create"] = action == "create"
            self.exit_requested = action == "exit"
            settable_event.set()
            return None

        if event_type == "cancelled":
            project, error_message = args
            if not isinstance(project, ImporterProject) or not isinstance(
                error_message, str
            ):
                raise ValueError("Invalid cancelled payload.")
            self.project = project
            self.worker = None
            self.console.print(error_message)
            self._print_project_status()
            if self.exit_requested:
                self.console.print("Leaving the import project paused and resumable.")
                return "exit"
            return "paused"

        if event_type == "finished":
            project = args[0]
            if not isinstance(project, ImporterProject):
                raise ValueError("Invalid finished payload.")
            self.project = project
            self.worker = None
            self.console.print(
                f"Import completed. Success: {project.success_count}. Failed: {project.failed_count}."
            )
            if project.failed_students:
                self._print_failed_students(project)
            self.project_manager.delete_project()
            self.project = None
            return "completed"

        if event_type == "stopped":
            project = args[0]
            if not isinstance(project, ImporterProject):
                raise ValueError("Invalid stopped payload.")
            self.project = project
            self.project.status = "paused"
            self.project_manager.save_project(self.project)
            self.worker = None
            self.console.print(
                f"Import paused at student {self.project.current_student}."
            )
            if self.exit_requested:
                self.console.print("Leaving the import project paused and resumable.")
                return "exit"
            return "paused"

        if event_type == "retry_progress":
            message, current, total, student_number, project = args
            if (
                not isinstance(message, str)
                or not isinstance(current, int)
                or not isinstance(total, int)
                or not isinstance(student_number, str)
                or not isinstance(project, ImporterProject)
            ):
                raise ValueError("Invalid retry progress payload.")
            self.project = project
            self._print_progress(
                f"{message} [retry {student_number}]",
                current,
                total,
                project,
            )
            return None

        if event_type == "retry_finished":
            project, student_number, was_successful, message = args
            if (
                not isinstance(project, ImporterProject)
                or not isinstance(student_number, str)
                or not isinstance(was_successful, bool)
                or not isinstance(message, str)
            ):
                raise ValueError("Invalid retry finished payload.")
            self.project = project
            self.retry_worker = None
            if was_successful:
                self.console.print(f"Retry succeeded for {student_number}.")
            else:
                self.console.print(f"Retry failed for {student_number}: {message}")
            if self.exit_requested:
                self.console.print("Leaving the import project paused and resumable.")
                return "exit"
            return "retry_finished"

        if event_type == "error":
            error_message = args[0]
            if not isinstance(error_message, str):
                raise ValueError("Invalid error payload.")
            self.console.print(error_message)
            return None

        raise ValueError(f"Unsupported worker event: {event_type}")

    def _request_pause(self, exit_after_pause: bool) -> None:
        if self.project is None:
            return

        self.exit_requested = exit_after_pause
        if self.worker and self.worker.is_alive():
            self.worker.stop()
            if exit_after_pause:
                self.console.print(
                    "Exit requested. The current student will finish before the CLI exits."
                )
            else:
                self.console.print(
                    "Pause requested. The current student will finish before the import pauses."
                )
            return

        self.project.status = "paused"
        self.project_manager.save_project(self.project)

    def _print_progress(
        self,
        message: str,
        current: int,
        total: int,
        project: ImporterProject,
    ) -> None:
        signature = (
            message,
            current,
            total,
            project.success_count,
            project.failed_count,
        )
        if signature == self.last_progress_signature:
            return
        self.last_progress_signature = signature
        percentage = int((current / total) * 100) if total else 0
        self.console.print(
            f"[{percentage:3d}%] {message} | current={project.current_student} | success={project.success_count} | failed={project.failed_count}"
        )

    def _prompt_paused_action(self) -> str:
        if self.project is None:
            return "exit"

        options: list[MenuOption] = [("resume", "Resume import"), ("status", "Show status")]
        if self.project.failed_students:
            next_failed = self.project.failed_students[0]
            options.append(("retry", f"Retry next failed student ({next_failed})"))
            options.append(("failed", "Show failed students"))
        options.append(("exit", "Exit CLI and keep the import paused"))
        return self.console.choose(
            f"Import project is {self.project.status}. Choose an action.",
            options,
            default="resume",
        )

    def _print_project_status(self) -> None:
        if self.project is None:
            self.console.print("No active import project was found.")
            return

        total_students = self.project_manager.count_students(
            self.project.start_student,
            self.project.end_student,
        )
        remaining_students = self.project_manager.count_remaining_students(self.project)
        completed_students = max(0, total_students - remaining_students)
        self.console.print(f"Range: {self.project.start_student} - {self.project.end_student}")
        self.console.print(f"Status: {self.project.status}")
        self.console.print(f"Current student: {self.project.current_student}")
        self.console.print(f"Completed students: {completed_students} of {total_students}")
        self.console.print(f"Successful imports: {self.project.success_count}")
        self.console.print(f"Failed imports: {self.project.failed_count}")
        if self.project.failed_students:
            preview = ", ".join(self.project.failed_students[:10])
            self.console.print(f"Failed students: {preview}")

    def _print_failed_students(self, project: ImporterProject | None = None) -> None:
        active_project = project or self.project
        if active_project is None or not active_project.failed_students:
            self.console.print("There are no failed students.")
            return

        self.console.print("Failed students:")
        for student_number in active_project.failed_students:
            self.console.print(f"- {student_number}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the student importer from the terminal using the same saved import project as the desktop importer."
    )
    parser.add_argument("--country", help="Override the saved country for this run")
    parser.add_argument("--start", help="First student number for a new import project")
    parser.add_argument("--end", help="Last student number for a new import project")
    parser.add_argument(
        "--auto-detect",
        action="store_true",
        help="Detect the first and last student numbers from CMS for a new import project",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Start running the existing saved import project immediately",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        dest="status_only",
        help="Show the saved import project status and exit",
    )
    parser.add_argument(
        "--student-info",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include student info data",
    )
    parser.add_argument(
        "--personal-info",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include personal info data",
    )
    parser.add_argument(
        "--education-history",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include education history data",
    )
    parser.add_argument(
        "--enrollment-data",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include enrollment, semester, and module data",
    )
    parser.add_argument(
        "--addresses",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include addresses and next-of-kin data",
    )
    parser.add_argument(
        "--skip-active-term",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Skip semester data for the active term",
    )
    parser.add_argument(
        "--delete-programs-before-import",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Delete existing program data before import",
    )
    return parser


def parse_options(argv: Sequence[str] | None = None) -> ImportCliOptions:
    args = build_parser().parse_args(argv)
    return ImportCliOptions(
        country=args.country,
        start=args.start,
        end=args.end,
        auto_detect=args.auto_detect,
        resume=args.resume,
        status_only=args.status_only,
        student_info=args.student_info,
        personal_info=args.personal_info,
        education_history=args.education_history,
        enrollment_data=args.enrollment_data,
        addresses=args.addresses,
        skip_active_term=args.skip_active_term,
        delete_programs_before_import=args.delete_programs_before_import,
    )


def build_import_options(options: ImportCliOptions) -> dict[str, bool]:
    return {
        "student_info": options.student_info,
        "personal_info": options.personal_info,
        "education_history": options.education_history,
        "enrollment_data": options.enrollment_data,
        "addresses": options.addresses,
        "skip_active_term": options.skip_active_term,
        "delete_programs_before_import": options.delete_programs_before_import,
    }


def has_selected_import_data(import_options: dict[str, bool]) -> bool:
    return any(
        import_options.get(key, False)
        for key in (
            "student_info",
            "personal_info",
            "education_history",
            "enrollment_data",
            "addresses",
        )
    )


def validate_student_range(start_student: str, end_student: str) -> tuple[str, str]:
    normalized_start = start_student.strip()
    normalized_end = end_student.strip()

    if not normalized_start or not normalized_end:
        raise ValueError("Please provide both first and last student numbers.")
    if not normalized_start.isdigit() or not normalized_end.isdigit():
        raise ValueError("Student numbers must be numeric.")
    if len(normalized_start) != 9 or len(normalized_end) != 9:
        raise ValueError("Student numbers must be exactly 9 digits.")
    if int(normalized_start) > int(normalized_end):
        raise ValueError(
            "First student number must be less than or equal to last student number."
        )
    if int(normalized_end) - int(normalized_start) > 20000:
        raise ValueError("Range is too large. Maximum 20,000 students at a time.")
    return normalized_start, normalized_end


def main(argv: Sequence[str] | None = None) -> int:
    options = parse_options(argv)
    cli = StudentImportCli()
    try:
        return cli.run(options)
    except KeyboardInterrupt:
        cli.console.print("Interrupted. Leaving the current import project unchanged.")
        return 130
    except Exception as exc:
        cli.console.print(f"Error: {exc}")
        return 1
