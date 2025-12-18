import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ImporterProject:
    start_student: str
    end_student: str
    current_student: str
    import_options: dict
    status: str
    success_count: int = 0
    failed_count: int = 0
    failed_students: Optional[list] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        if self.failed_students is None:
            self.failed_students = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()


class ImporterProjectManager:
    PROJECT_FILE = Path.home() / ".registry" / "import_project.json"

    @classmethod
    def _ensure_directory(cls):
        cls.PROJECT_FILE.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def create_project(
        cls, start_student: str, end_student: str, import_options: dict
    ) -> ImporterProject:
        cls._ensure_directory()

        project = ImporterProject(
            start_student=start_student,
            end_student=end_student,
            current_student=start_student,
            import_options=import_options,
            status="pending",
        )

        cls.save_project(project)
        return project

    @classmethod
    def load_project(cls) -> Optional[ImporterProject]:
        if not cls.PROJECT_FILE.exists():
            return None

        try:
            with open(cls.PROJECT_FILE, "r") as f:
                data = json.load(f)
            return ImporterProject(**data)
        except Exception:
            return None

    @classmethod
    def save_project(cls, project: ImporterProject):
        cls._ensure_directory()

        project.updated_at = datetime.now().isoformat()

        with open(cls.PROJECT_FILE, "w") as f:
            json.dump(asdict(project), f, indent=2)

    @classmethod
    def delete_project(cls):
        if cls.PROJECT_FILE.exists():
            cls.PROJECT_FILE.unlink()

    @classmethod
    def has_active_project(cls) -> bool:
        project = cls.load_project()
        if not project:
            return False
        return project.status in ["pending", "running", "paused"]

    @classmethod
    def generate_student_numbers(cls, start: str, end: str) -> list[str]:
        try:
            start_num = int(start)
            end_num = int(end)

            if start_num > end_num:
                return []

            return [str(num).zfill(9) for num in range(start_num, end_num + 1)]
        except Exception:
            return []

    @classmethod
    def get_remaining_students(cls, project: ImporterProject) -> list[str]:
        all_students = cls.generate_student_numbers(
            project.start_student, project.end_student
        )

        current_idx = 0
        try:
            current_idx = all_students.index(project.current_student)
        except ValueError:
            pass

        return all_students[current_idx:]
