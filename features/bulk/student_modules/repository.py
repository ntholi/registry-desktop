from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from base import get_logger
from database import (
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
    get_engine,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class StudentModuleRow:
    std_no: str
    name: Optional[str]
    student_module_id: int
    semester_module_id: int
    module_code: str
    module_name: str
    status: str
    credits: Optional[float]
    marks: Optional[str]
    grade: Optional[str]
    student_semester_id: int


class BulkStudentModulesRepository:
    def __init__(self) -> None:
        self._engine = get_engine()

    @contextmanager
    def _session(self):
        with Session(self._engine) as session:
            yield session

    def list_active_schools(self):
        with self._session() as session:
            return (
                session.query(School.id, School.name)
                .filter(School.is_active == True)
                .order_by(School.name)
                .all()
            )

    def list_programs(self, school_id: Optional[int] = None):
        with self._session() as session:
            query = session.query(Program.id, Program.name)
            if school_id:
                query = query.filter(Program.school_id == school_id)
            return query.order_by(Program.name).all()

    def list_structures(self, program_id: Optional[int] = None):
        with self._session() as session:
            query = session.query(Structure.id, Structure.code, Structure.desc)
            if program_id:
                query = query.filter(Structure.program_id == program_id)
            return query.order_by(Structure.code.desc()).all()

    def list_structure_modules(self, structure_id: int):
        """List all modules available in a structure."""
        with self._session() as session:
            results = (
                session.query(
                    SemesterModule.id.label("semester_module_id"),
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
                .filter(StructureSemester.structure_id == structure_id)
                .order_by(StructureSemester.semester_number, Module.code)
                .all()
            )
            return results

    def list_semester_numbers(self, structure_id: int):
        """List all semester numbers in a structure."""
        with self._session() as session:
            results = (
                session.query(StructureSemester.semester_number)
                .filter(StructureSemester.structure_id == structure_id)
                .distinct()
                .order_by(StructureSemester.semester_number)
                .all()
            )
            return [r[0] for r in results]

    def list_terms(self, structure_id: int):
        """List all unique terms for students enrolled in a structure."""
        with self._session() as session:
            results = (
                session.query(StudentSemester.term)
                .join(
                    StudentProgram,
                    StudentSemester.student_program_id == StudentProgram.id,
                )
                .filter(StudentProgram.structure_id == structure_id)
                .distinct()
                .order_by(StudentSemester.term.desc())
                .all()
            )
            return [r[0] for r in results]

    def fetch_students_with_module(
        self,
        semester_module_id: int,
        structure_id: int,
        term: Optional[str] = None,
    ) -> list[StudentModuleRow]:
        """Fetch all students who have a specific module in their enrollment."""
        with self._session() as session:
            query = (
                session.query(
                    Student.std_no,
                    Student.name,
                    StudentModule.id.label("student_module_id"),
                    StudentModule.semester_module_id,
                    Module.code.label("module_code"),
                    Module.name.label("module_name"),
                    StudentModule.status,
                    SemesterModule.credits,
                    StudentModule.marks,
                    StudentModule.grade,
                    StudentModule.student_semester_id,
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
                .filter(StudentModule.semester_module_id == semester_module_id)
                .filter(StudentProgram.structure_id == structure_id)
                .filter(
                    or_(
                        StudentProgram.status == "Active",
                        StudentProgram.status == "Completed",
                    )
                )
            )

            if term:
                query = query.filter(StudentSemester.term == term)

            query = query.order_by(Student.std_no.desc())
            results = query.all()

            return [
                StudentModuleRow(
                    std_no=str(r.std_no),
                    name=r.name,
                    student_module_id=r.student_module_id,
                    semester_module_id=r.semester_module_id,
                    module_code=r.module_code,
                    module_name=r.module_name,
                    status=r.status,
                    credits=r.credits,
                    marks=r.marks,
                    grade=r.grade,
                    student_semester_id=r.student_semester_id,
                )
                for r in results
            ]

    def search_semester_modules(self, search_query: str):
        with self._session() as session:
            search_pattern = f"%{search_query}%"

            results = (
                session.query(
                    SemesterModule.id.label("semester_module_id"),
                    Module.code.label("module_code"),
                    Module.name.label("module_name"),
                    Program.name.label("program_name"),
                    SemesterModule.credits,
                    StructureSemester.semester_number,
                )
                .join(Module, SemesterModule.module_id == Module.id)
                .join(
                    StructureSemester,
                    SemesterModule.semester_id == StructureSemester.id,
                )
                .join(Structure, StructureSemester.structure_id == Structure.id)
                .join(Program, Structure.program_id == Program.id)
                .filter(
                    or_(
                        Module.code.like(search_pattern),
                        Module.name.like(search_pattern),
                    )
                )
                .order_by(Module.code, Program.name)
                .all()
            )

            return [
                {
                    "semester_module_id": r.semester_module_id,
                    "module_code": r.module_code,
                    "module_name": r.module_name,
                    "program_name": r.program_name,
                    "credits": r.credits,
                    "semester_number": r.semester_number,
                }
                for r in results
            ]

    def fetch_students_by_module_search(
        self,
        structure_id: int,
        search_query: str,
        term: Optional[str] = None,
    ) -> list[StudentModuleRow]:
        with self._session() as session:
            search_pattern = f"%{search_query}%"

            query = (
                session.query(
                    Student.std_no,
                    Student.name,
                    StudentModule.id.label("student_module_id"),
                    StudentModule.semester_module_id,
                    Module.code.label("module_code"),
                    Module.name.label("module_name"),
                    StudentModule.status,
                    SemesterModule.credits,
                    StudentModule.marks,
                    StudentModule.grade,
                    StudentModule.student_semester_id,
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
                .filter(StudentProgram.structure_id == structure_id)
                .filter(
                    or_(
                        Module.code.like(search_pattern),
                        Module.name.like(search_pattern),
                    )
                )
                .filter(
                    or_(
                        StudentProgram.status == "Active",
                        StudentProgram.status == "Completed",
                    )
                )
            )

            if term:
                query = query.filter(StudentSemester.term == term)

            query = query.order_by(Student.std_no.desc())
            results = query.all()

            return [
                StudentModuleRow(
                    std_no=str(r.std_no),
                    name=r.name,
                    student_module_id=r.student_module_id,
                    semester_module_id=r.semester_module_id,
                    module_code=r.module_code,
                    module_name=r.module_name,
                    status=r.status,
                    credits=r.credits,
                    marks=r.marks,
                    grade=r.grade,
                    student_semester_id=r.student_semester_id,
                )
                for r in results
            ]
