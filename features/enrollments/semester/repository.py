from __future__ import annotations

from typing import Optional

from features.sync.students.repository import StudentRepository


class SemesterEnrollmentRepository:
    def __init__(self, student_repository: Optional[StudentRepository] = None) -> None:
        self._student_repo = student_repository or StudentRepository()

    def get_student_program_details_by_id(self, student_program_id: int):
        return self._student_repo.get_student_program_details_by_id(student_program_id)

    def get_student_semester_by_id(self, student_semester_id: int):
        return self._student_repo.get_student_semester_by_id(student_semester_id)

    def upsert_student_semester(
        self, student_program_id: int, data: dict
    ) -> tuple[bool, str, Optional[int]]:
        return self._student_repo.upsert_student_semester(student_program_id, data)

    def get_semester_module_credits(self, semester_module_id: int) -> Optional[float]:
        return self._student_repo.get_semester_module_credits(semester_module_id)

    def upsert_student_module(self, data: dict) -> tuple[bool, str]:
        return self._student_repo.upsert_student_module(data)
