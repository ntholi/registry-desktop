from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from base import get_logger
from database import (
    Assessment,
    AssessmentMark,
    Module,
    Program,
    School,
    SemesterModule,
    Structure,
    StructureSemester,
    Student,
    StudentModule,
    StudentProgram,
    StudentSemester,
    Term,
    get_engine,
)
from database.models import Grade

logger = get_logger(__name__)


@dataclass(frozen=True)
class StudentModuleGradeRow:
    std_no: str
    name: Optional[str]
    student_module_db_id: int
    semester_module_db_id: int
    semester_module_cms_id: Optional[int]
    module_db_id: int
    module_code: str
    module_name: str
    status: str
    credits: Optional[float]
    marks: Optional[str]
    grade: Optional[str]
    student_semester_db_id: int
    term_db_id: int


@dataclass(frozen=True)
class AssessmentData:
    id: int
    weight: float
    total_marks: float


@dataclass(frozen=True)
class AssessmentMarkData:
    assessment_id: int
    marks: float


class ModuleGradesRepository:
    def __init__(self) -> None:
        self._engine = get_engine()

    @contextmanager
    def _session(self):
        with Session(self._engine) as session:
            yield session

    def list_active_schools(self):
        with self._session() as session:
            return (
                session.query(School.cms_id.label("cms_id"), School.name)
                .filter(School.is_active == True)
                .filter(School.cms_id.isnot(None))
                .order_by(School.name)
                .all()
            )

    def list_programs(self, school_id: Optional[int] = None):
        with self._session() as session:
            query = session.query(Program.cms_id.label("cms_id"), Program.name).filter(
                Program.cms_id.isnot(None)
            )
            if school_id:
                query = query.join(School, Program.school_id == School.id).filter(
                    School.cms_id == school_id
                )
            return query.order_by(Program.name).all()

    def list_structures(self, program_id: Optional[int] = None):
        with self._session() as session:
            query = session.query(
                Structure.cms_id.label("cms_id"), Structure.code, Structure.desc
            ).filter(Structure.cms_id.isnot(None))
            if program_id:
                query = query.join(Program, Structure.program_id == Program.id).filter(
                    Program.cms_id == program_id
                )
            return query.order_by(Structure.code.desc()).all()

    def list_structure_modules(self, structure_id: int):
        with self._session() as session:
            results = (
                session.query(
                    SemesterModule.cms_id.label("semester_module_cms_id"),
                    Module.code.label("module_code"),
                    Module.name.label("module_name"),
                    SemesterModule.credits,
                    StructureSemester.semester_number,
                )
                .join(Module, SemesterModule.module_id == Module.id)
                .join(
                    StructureSemester,
                    SemesterModule.semester_id == StructureSemester.id,
                )
                .join(Structure, StructureSemester.structure_id == Structure.id)
                .filter(Structure.cms_id == structure_id)
                .filter(SemesterModule.cms_id.isnot(None))
                .order_by(StructureSemester.semester_number, Module.code)
                .all()
            )
            return results

    def list_terms(self, structure_id: int):
        with self._session() as session:
            results = (
                session.query(StudentSemester.term_code)
                .join(
                    StudentProgram,
                    StudentSemester.student_program_id == StudentProgram.id,
                )
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .filter(Structure.cms_id == structure_id)
                .distinct()
                .order_by(StudentSemester.term_code.desc())
                .all()
            )
            return [r[0] for r in results]

    def fetch_students_with_module(
        self,
        structure_id: int,
        semester_module_id: Optional[int] = None,
        term: Optional[str] = None,
    ) -> list[StudentModuleGradeRow]:
        with self._session() as session:
            term_subquery = (
                session.query(Term.id)
                .filter(Term.code == StudentSemester.term_code)
                .correlate(StudentSemester)
                .scalar_subquery()
            )

            query = (
                session.query(
                    Student.std_no,
                    Student.name,
                    StudentModule.id.label("student_module_db_id"),
                    StudentModule.semester_module_id.label("semester_module_db_id"),
                    SemesterModule.cms_id.label("semester_module_cms_id"),
                    Module.id.label("module_db_id"),
                    Module.code.label("module_code"),
                    Module.name.label("module_name"),
                    StudentModule.status,
                    StudentModule.credits,
                    StudentModule.marks,
                    StudentModule.grade,
                    StudentModule.student_semester_id.label("student_semester_db_id"),
                    term_subquery.label("term_db_id"),
                )
                .join(
                    StudentSemester,
                    StudentModule.student_semester_id == StudentSemester.id,
                )
                .join(
                    StudentProgram,
                    StudentSemester.student_program_id == StudentProgram.id,
                )
                .join(Student, StudentProgram.std_no == Student.std_no)
                .join(
                    SemesterModule,
                    StudentModule.semester_module_id == SemesterModule.id,
                )
                .join(Module, SemesterModule.module_id == Module.id)
                .join(
                    StructureSemester,
                    StudentSemester.structure_semester_id == StructureSemester.id,
                )
                .filter(Structure.cms_id == structure_id)
                .filter(
                    or_(
                        StudentProgram.status == "Active",
                        StudentProgram.status == "Completed",
                    )
                )
            )

            if semester_module_id:
                query = query.filter(SemesterModule.cms_id == semester_module_id)

            if term:
                query = query.filter(StudentSemester.term_code == term)

            query = query.order_by(Student.std_no.desc())
            results = query.all()

            return [
                StudentModuleGradeRow(
                    std_no=str(r.std_no),
                    name=r.name,
                    student_module_db_id=r.student_module_db_id,
                    semester_module_db_id=r.semester_module_db_id,
                    semester_module_cms_id=r.semester_module_cms_id,
                    module_db_id=r.module_db_id,
                    module_code=r.module_code,
                    module_name=r.module_name,
                    status=r.status,
                    credits=r.credits,
                    marks=r.marks,
                    grade=r.grade,
                    student_semester_db_id=r.student_semester_db_id,
                    term_db_id=r.term_db_id,
                )
                for r in results
            ]

    def get_assessments_for_module(
        self, module_id: int, term_id: int
    ) -> list[AssessmentData]:
        with self._session() as session:
            results = (
                session.query(
                    Assessment.id,
                    Assessment.weight,
                    Assessment.total_marks,
                )
                .filter(Assessment.module_id == module_id)
                .filter(Assessment.term_id == term_id)
                .all()
            )
            return [
                AssessmentData(
                    id=r.id,
                    weight=r.weight,
                    total_marks=r.total_marks,
                )
                for r in results
            ]

    def get_assessment_marks_for_student_module(
        self, student_module_id: int
    ) -> list[AssessmentMarkData]:
        with self._session() as session:
            results = (
                session.query(
                    AssessmentMark.assessment_id,
                    AssessmentMark.marks,
                )
                .filter(AssessmentMark.student_module_id == student_module_id)
                .all()
            )
            return [
                AssessmentMarkData(
                    assessment_id=r.assessment_id,
                    marks=r.marks,
                )
                for r in results
            ]

    def update_student_module_grade(
        self,
        student_module_id: int,
        marks: str,
        grade: Grade,
    ) -> bool:
        with self._session() as session:
            try:
                student_module = session.query(StudentModule).get(student_module_id)
                if student_module:
                    student_module.marks = marks
                    student_module.grade = grade
                    session.commit()
                    return True
                return False
            except Exception as e:
                logger.error(f"Error updating student module grade: {e}")
                session.rollback()
                return False
