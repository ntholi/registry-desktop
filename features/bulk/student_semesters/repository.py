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
    student_semester_db_id: int
    student_semester_cms_id: Optional[int]
    structure_semester_db_id: int
    structure_semester_cms_id: Optional[int]
    semester_number: str
    term_code: str
    status: str
    student_program_db_id: int


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

    def list_semester_numbers(self, structure_id: int):
        with self._session() as session:
            results = (
                session.query(
                    StructureSemester.cms_id.label("cms_id"),
                    StructureSemester.semester_number,
                )
                .join(Structure, StructureSemester.structure_id == Structure.id)
                .filter(Structure.cms_id == structure_id)
                .filter(StructureSemester.cms_id.isnot(None))
                .order_by(StructureSemester.semester_number)
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
                    StudentSemester.id.label("student_semester_db_id"),
                    StudentSemester.cms_id.label("student_semester_cms_id"),
                    StudentSemester.structure_semester_id.label(
                        "structure_semester_db_id"
                    ),
                    StructureSemester.cms_id.label("structure_semester_cms_id"),
                    StructureSemester.semester_number,
                    StudentSemester.term_code,
                    StudentSemester.status,
                    StudentSemester.student_program_id.label("student_program_db_id"),
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
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .filter(StructureSemester.cms_id == structure_semester_id)
                .filter(Structure.cms_id == structure_id)
                .filter(
                    or_(
                        StudentProgram.status == "Active",
                        StudentProgram.status == "Completed",
                    )
                )
            )

            if term:
                query = query.filter(StudentSemester.term_code == term)

            query = query.order_by(Student.std_no.desc())
            results = query.all()

            return [
                StudentSemesterRow(
                    std_no=str(r.std_no),
                    name=r.name,
                    student_semester_db_id=r.student_semester_db_id,
                    student_semester_cms_id=r.student_semester_cms_id,
                    structure_semester_db_id=r.structure_semester_db_id,
                    structure_semester_cms_id=r.structure_semester_cms_id,
                    semester_number=r.semester_number,
                    term_code=r.term_code,
                    status=r.status,
                    student_program_db_id=r.student_program_db_id,
                )
                for r in results
            ]

    def search_semester_modules(self, search_query: str):
        with self._session() as session:
            search_pattern = f"%{search_query}%"

            results = (
                session.query(
                    SemesterModule.cms_id.label("semester_module_cms_id"),
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
                .filter(SemesterModule.cms_id.isnot(None))
                .order_by(Module.code, Program.name)
                .all()
            )

            return [
                {
                    "semester_module_cms_id": r.semester_module_cms_id,
                    "module_code": r.module_code,
                    "module_name": r.module_name,
                    "program_name": r.program_name,
                    "credits": r.credits,
                    "semester_number": r.semester_number,
                }
                for r in results
            ]
