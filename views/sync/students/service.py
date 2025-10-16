from __future__ import annotations

from typing import Optional

from .repository import StudentRepository
from .scraper import scrape_student_data


class StudentSyncService:
    def __init__(self, repository: Optional[StudentRepository] = None) -> None:
        self._repository = repository or StudentRepository()

    def pull_student(self, student_number: str) -> bool:
        scraped_data = scrape_student_data(student_number)
        if not scraped_data:
            return False
        return self._repository.update_student(student_number, scraped_data)
