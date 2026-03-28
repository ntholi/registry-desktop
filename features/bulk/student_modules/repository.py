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
    student_module_db_id: int
    student_module_cms_id: Optional[int]
    semester_module_db_id: int
    semester_module_cms_id: Optional[int]
    module_code: str
    module_name: str
    status: str
    credits: Optional[float]
    marks: Optional[str]
    grade: Optional[str]
    student_semester_db_id: int


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
                session.query(School.cms_id.label("cms_id"), School.name)
                .filter(School.is_active == True)
                .filter(School.cms_id.isnot(None))
                .order_by(School.name)
                .all()
            )

    def list_programs(self, school_cms_id: Optional[int] = None):
        with self._session() as session:
            query = session.query(Program.cms_id.label("cms_id"), Program.name).filter(
                Program.cms_id.isnot(None)
            )
            if school_cms_id:
                query = query.join(School, Program.school_id == School.id).filter(
                    School.cms_id == school_cms_id
                )
            return query.order_by(Program.name).all()

    def list_structures(self, program_cms_id: Optional[int] = None):
        with self._session() as session:
            query = session.query(
                Structure.cms_id.label("cms_id"), Structure.code, Structure.desc
            ).filter(Structure.cms_id.isnot(None))
            if program_cms_id:
                query = query.join(Program, Structure.program_id == Program.id).filter(
                    Program.cms_id == program_cms_id
                )
            return query.order_by(Structure.code.desc()).all()

    def list_structure_modules(self, structure_cms_id: int):
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
                .filter(Structure.cms_id == structure_cms_id)
                .filter(SemesterModule.cms_id.isnot(None))
                .order_by(StructureSemester.semester_number, Module.code)
                .all()
            )
            return results

    def list_semester_numbers(self, structure_cms_id: int):
        with self._session() as session:
            results = (
                session.query(StructureSemester.semester_number)
                .join(Structure, StructureSemester.structure_id == Structure.id)
                .filter(Structure.cms_id == structure_cms_id)
                .distinct()
                .order_by(StructureSemester.semester_number)
                .all()
            )
            return [r[0] for r in results]

    def list_terms(self, structure_cms_id: int):
        with self._session() as session:
            results = (
                session.query(StudentSemester.term_code)
                .join(
                    StudentProgram,
                    StudentSemester.student_program_id == StudentProgram.id,
                )
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .filter(Structure.cms_id == structure_cms_id)
                .distinct()
                .order_by(StudentSemester.term_code.desc())
                .all()
            )
            return [r[0] for r in results]

    def fetch_students_with_module(
        self,
        semester_module_cms_id: int,
        structure_cms_id: int,
        term: Optional[str] = None,
    ) -> list[StudentModuleRow]:
        with self._session() as session:
            query = (
                session.query(
                    Student.std_no,
                    Student.name,
                    StudentModule.id.label("student_module_db_id"),
                    StudentModule.cms_id.label("student_module_cms_id"),
                    StudentModule.semester_module_id.label("semester_module_db_id"),
                    SemesterModule.cms_id.label("semester_module_cms_id"),
                    Module.code.label("module_code"),
                    Module.name.label("module_name"),
                    StudentModule.status,
                    StudentModule.credits,
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
                .join(Structure, StructureSemester.structure_id == Structure.id)
                .filter(SemesterModule.cms_id == semester_module_cms_id)
                .filter(Structure.cms_id == structure_cms_id)
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
                StudentModuleRow(
                    std_no=str(r.std_no),
                    name=r.name,
                    student_module_db_id=r.student_module_db_id,
                    student_module_cms_id=r.student_module_cms_id,
                    semester_module_db_id=r.semester_module_db_id,
                    semester_module_cms_id=r.semester_module_cms_id,
                    module_code=r.module_code,
                    module_name=r.module_name,
                    status=r.status,
                    credits=r.credits,
                    marks=r.marks,
                    grade=r.grade,
                    student_semester_db_id=r.student_semester_id,
                )
                for r in results
            ]

    def search_semester_modules(self, search_query: str):
        with self._session() as session:
            search_pattern = f"%{search_query}%"

            results = (
                session.query(
                    SemesterModule.id.label("semester_module_db_id"),
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
                    "semester_module_db_id": r.semester_module_db_id,
                    "semester_module_cms_id": r.semester_module_cms_id,
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
        structure_cms_id: int,
        search_query: str,
        term: Optional[str] = None,
    ) -> list[StudentModuleRow]:
        with self._session() as session:
            search_pattern = f"%{search_query}%"

            query = (
                session.query(
                    Student.std_no,
                    Student.name,
                    StudentModule.id.label("student_module_db_id"),
                    StudentModule.cms_id.label("student_module_cms_id"),
                    StudentModule.semester_module_id.label("semester_module_db_id"),
                    SemesterModule.cms_id.label("semester_module_cms_id"),
                    Module.code.label("module_code"),
                    Module.name.label("module_name"),
                    StudentModule.status,
                    StudentModule.credits,
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
                .join(Structure, StructureSemester.structure_id == Structure.id)
                .filter(Structure.cms_id == structure_cms_id)
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
                query = query.filter(StudentSemester.term_code == term)

            query = query.order_by(Student.std_no.desc())
            results = query.all()

            return [
                StudentModuleRow(
                    std_no=str(r.std_no),
                    name=r.name,
                    student_module_db_id=r.student_module_db_id,
                    student_module_cms_id=r.student_module_cms_id,
                    semester_module_db_id=r.semester_module_db_id,
                    semester_module_cms_id=r.semester_module_cms_id,
                    module_code=r.module_code,
                    module_name=r.module_name,
                    status=r.status,
                    credits=r.credits,
                    marks=r.marks,
                    grade=r.grade,
                    student_semester_db_id=r.student_semester_id,
                )
                for r in results
            ]
