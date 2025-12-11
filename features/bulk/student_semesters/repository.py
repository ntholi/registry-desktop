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
    StudentProgram,
    StudentSemester,
    get_engine,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class StudentSemesterRow:
    std_no: str
    name: Optional[str]
    student_semester_id: int
    structure_semester_id: int
    semester_number: str
    term: str
    status: str
    student_program_id: int


class BulkStudentSemestersRepository:
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

    def list_semester_numbers(self, structure_id: int):
        with self._session() as session:
            results = (
                session.query(
                    StructureSemester.id,
                    StructureSemester.semester_number,
                )
                .filter(StructureSemester.structure_id == structure_id)
                .order_by(StructureSemester.semester_number)
                .all()
            )
            return results

    def list_terms(self, structure_id: int):
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

    def fetch_students_by_semester(
        self,
        structure_semester_id: int,
        structure_id: int,
        term: Optional[str] = None,
    ) -> list[StudentSemesterRow]:
        with self._session() as session:
            query = (
                session.query(
                    Student.std_no,
                    Student.name,
                    StudentSemester.id.label("student_semester_id"),
                    StudentSemester.structure_semester_id,
                    StructureSemester.semester_number,
                    StudentSemester.term,
                    StudentSemester.status,
                    StudentSemester.student_program_id,
                )
                .join(
                    StudentProgram,
                    StudentSemester.student_program_id == StudentProgram.id,
                )
                .join(Student, StudentProgram.std_no == Student.std_no)
                .join(
                    StructureSemester,
                    StudentSemester.structure_semester_id == StructureSemester.id,
                )
                .filter(StudentSemester.structure_semester_id == structure_semester_id)
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
                StudentSemesterRow(
                    std_no=str(r.std_no),
                    name=r.name,
                    student_semester_id=r.student_semester_id,
                    structure_semester_id=r.structure_semester_id,
                    semester_number=r.semester_number,
                    term=r.term,
                    status=r.status,
                    student_program_id=r.student_program_id,
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
