from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from base import get_logger
from utils.grades import get_letter_grade

from .repository import (
    AssessmentData,
    AssessmentMarkData,
    ModuleGradesRepository,
    StudentModuleGradeRow,
)

logger = get_logger(__name__)

SKIP_GRADES = {"ANN", "DNS", "EXP", "DEF"}


@dataclass
class GradeCalculation:
    weighted_total: int
    grade: str
    has_marks: bool
    has_passed: bool


def calculate_module_grade(
    assessments: list[AssessmentData],
    assessment_marks: list[AssessmentMarkData],
) -> GradeCalculation:
    total_weight = 0.0
    weighted_marks = 0.0
    has_marks = False

    for assessment in assessments:
        total_weight += assessment.weight

        mark_record = next(
            (m for m in assessment_marks if m.assessment_id == assessment.id),
            None,
        )

        if mark_record is not None and mark_record.marks is not None:
            percentage = mark_record.marks / assessment.total_marks
            weighted_marks += percentage * assessment.weight
            has_marks = True

    weighted_total = round(weighted_marks)
    grade = get_letter_grade(weighted_total)
    has_passed = weighted_total >= total_weight * 0.5

    return GradeCalculation(
        weighted_total=weighted_total,
        grade=grade,
        has_marks=has_marks,
        has_passed=has_passed,
    )


class ModuleGradesService:
    def __init__(self, repository: ModuleGradesRepository):
        self.repository = repository

    def recalculate_grade(
        self,
        student_module: StudentModuleGradeRow,
        skip_pp: bool,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, str, Optional[GradeCalculation]]:
        current_grade = (student_module.grade or "").upper()

        if current_grade in SKIP_GRADES:
            return (
                False,
                f"Skipped - grade is {current_grade}",
                None,
            )

        if skip_pp and current_grade == "PP":
            return (
                False,
                "Skipped - grade is PP (skip PP option enabled)",
                None,
            )

        if progress_callback:
            progress_callback(f"Fetching assessments for {student_module.std_no}...")

        if not student_module.term_id:
            return (
                False,
                "No term found for student module",
                None,
            )

        assessments = self.repository.get_assessments_for_module(
            student_module.module_id,
            student_module.term_id,
        )

        if not assessments:
            return (
                False,
                "No assessments found for this module/term",
                None,
            )

        if progress_callback:
            progress_callback(f"Fetching marks for {student_module.std_no}...")

        assessment_marks = self.repository.get_assessment_marks_for_student_module(
            student_module.student_module_id,
        )

        if not assessment_marks:
            return (
                False,
                "No assessment marks found",
                None,
            )

        calculation = calculate_module_grade(assessments, assessment_marks)

        if not calculation.has_marks:
            return (
                False,
                "No marks available for calculation",
                None,
            )

        new_marks = str(calculation.weighted_total)
        new_grade = calculation.grade

        if new_marks == student_module.marks and new_grade == student_module.grade:
            return (
                True,
                "Grade is already correct",
                calculation,
            )

        if progress_callback:
            progress_callback(
                f"Updating {student_module.std_no}: {student_module.marks} -> {new_marks}, "
                f"{student_module.grade} -> {new_grade}..."
            )

        success = self.repository.update_student_module_grade(
            student_module.student_module_id,
            new_marks,
            new_grade,
        )

        if success:
            return (
                True,
                f"Updated: {student_module.marks} -> {new_marks}, "
                f"{student_module.grade} -> {new_grade}",
                calculation,
            )
        else:
            return (
                False,
                "Failed to update database",
                None,
            )
