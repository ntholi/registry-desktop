from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from base import get_logger
from database import Program, School, Structure, Student, StudentProgram, get_engine

logger = get_logger(__name__)


@dataclass(frozen=True)
class StudentProgramRow:
    std_no: str
    name: Optional[str]
    student_program_db_id: int
    student_program_cms_id: Optional[int]
    structure_db_id: int
    structure_cms_id: Optional[int]
    structure_code: str
    intake_date: Optional[str]
    reg_date: Optional[str]
    start_term: Optional[str]
    stream: Optional[str]
    status: str
    assist_provider: Optional[str]
    graduation_date: Optional[str]
    program_cms_id: Optional[int]
    program_code: str


@dataclass(frozen=True)
class StructureOption:
    db_id: int
    cms_id: int
    code: str
    desc: Optional[str]


class BulkStudentProgramsRepository:
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
            query = session.query(
                Program.cms_id.label("cms_id"), Program.name, Program.code
            ).filter(Program.cms_id.isnot(None))
            if school_id:
                query = query.join(School, Program.school_id == School.id).filter(
                    School.cms_id == school_id
                )
            return query.order_by(Program.name).all()

    def list_terms_for_program(self, program_id: int):
        with self._session() as session:
            results = (
                session.query(StudentProgram.start_term)
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .join(Program, Structure.program_id == Program.id)
                .filter(Program.cms_id == program_id)
                .filter(StudentProgram.start_term.isnot(None))
                .filter(StudentProgram.start_term != "")
                .distinct()
                .order_by(StudentProgram.start_term.desc())
                .all()
            )
            return [r[0] for r in results if r[0]]

    def list_structures_for_program(self, program_id: int):
        with self._session() as session:
            results = (
                session.query(
                    Structure.id.label("db_id"),
                    Structure.cms_id.label("cms_id"),
                    Structure.code,
                    Structure.desc,
                )
                .join(Program, Structure.program_id == Program.id)
                .filter(Program.cms_id == program_id)
                .filter(Structure.cms_id.isnot(None))
                .order_by(Structure.code.desc())
                .all()
            )
            return [
                StructureOption(
                    db_id=r.db_id,
                    cms_id=r.cms_id,
                    code=r.code,
                    desc=r.desc,
                )
                for r in results
            ]

    def fetch_students_by_program_and_term(
        self,
        program_id: int,
        term: Optional[str] = None,
    ) -> list[StudentProgramRow]:
        with self._session() as session:
            query = (
                session.query(
                    Student.std_no,
                    Student.name,
                    StudentProgram.id.label("student_program_db_id"),
                    StudentProgram.cms_id.label("student_program_cms_id"),
                    StudentProgram.structure_id.label("structure_db_id"),
                    Structure.cms_id.label("structure_cms_id"),
                    Structure.code.label("structure_code"),
                    StudentProgram.intake_date,
                    StudentProgram.reg_date,
                    StudentProgram.start_term,
                    StudentProgram.stream,
                    StudentProgram.status,
                    StudentProgram.assist_provider,
                    StudentProgram.graduation_date,
                    Program.cms_id.label("program_cms_id"),
                    Program.code.label("program_code"),
                )
                .join(Student, StudentProgram.std_no == Student.std_no)
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .join(Program, Structure.program_id == Program.id)
                .filter(Program.cms_id == program_id)
                .filter(
                    or_(
                        StudentProgram.status == "Active",
                        StudentProgram.status == "Completed",
                    )
                )
            )

            if term:
                query = query.filter(StudentProgram.start_term == term)

            query = query.order_by(Student.std_no.desc())
            results = query.all()

            return [
                StudentProgramRow(
                    std_no=str(r.std_no),
                    name=r.name,
                    student_program_db_id=r.student_program_db_id,
                    student_program_cms_id=r.student_program_cms_id,
                    structure_db_id=r.structure_db_id,
                    structure_cms_id=r.structure_cms_id,
                    structure_code=r.structure_code,
                    intake_date=r.intake_date,
                    reg_date=r.reg_date,
                    start_term=r.start_term,
                    stream=r.stream,
                    status=r.status,
                    assist_provider=r.assist_provider,
                    graduation_date=r.graduation_date,
                    program_cms_id=r.program_cms_id,
                    program_code=r.program_code,
                )
                for r in results
            ]

    def get_student_program_by_id(
        self, student_program_id: int
    ) -> Optional[StudentProgramRow]:
        with self._session() as session:
            result = (
                session.query(
                    Student.std_no,
                    Student.name,
                    StudentProgram.id.label("student_program_db_id"),
                    StudentProgram.cms_id.label("student_program_cms_id"),
                    StudentProgram.structure_id.label("structure_db_id"),
                    Structure.cms_id.label("structure_cms_id"),
                    Structure.code.label("structure_code"),
                    StudentProgram.intake_date,
                    StudentProgram.reg_date,
                    StudentProgram.start_term,
                    StudentProgram.stream,
                    StudentProgram.status,
                    StudentProgram.assist_provider,
                    StudentProgram.graduation_date,
                    Program.cms_id.label("program_cms_id"),
                    Program.code.label("program_code"),
                )
                .join(Student, StudentProgram.std_no == Student.std_no)
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .join(Program, Structure.program_id == Program.id)
                .filter(StudentProgram.id == student_program_id)
                .first()
            )

            if not result:
                return None

            return StudentProgramRow(
                std_no=str(result.std_no),
                name=result.name,
                student_program_db_id=result.student_program_db_id,
                student_program_cms_id=result.student_program_cms_id,
                structure_db_id=result.structure_db_id,
                structure_cms_id=result.structure_cms_id,
                structure_code=result.structure_code,
                intake_date=result.intake_date,
                reg_date=result.reg_date,
                start_term=result.start_term,
                stream=result.stream,
                status=result.status,
                assist_provider=result.assist_provider,
                graduation_date=result.graduation_date,
                program_cms_id=result.program_cms_id,
                program_code=result.program_code,
            )

    def update_student_program_structure(
        self, student_program_id: int, new_structure_id: int
    ) -> tuple[bool, str]:
        with self._session() as session:
            try:
                student_program = (
                    session.query(StudentProgram)
                    .filter(StudentProgram.id == student_program_id)
                    .first()
                )

                if not student_program:
                    return False, "Student program not found"

                student_program.structure_id = new_structure_id
                session.commit()

                logger.info(
                    f"Updated student program {student_program_id} "
                    f"structure to {new_structure_id}"
                )
                return True, "Structure updated successfully"

            except Exception as e:
                session.rollback()
                logger.error(
                    f"Error updating student program structure - "
                    f"student_program_id={student_program_id}, "
                    f"new_structure_id={new_structure_id}, error={str(e)}"
                )
                return False, str(e)

    def get_cms_student_program_id(self, student_program_id: int) -> Optional[int]:
        with self._session() as session:
            result = (
                session.query(StudentProgram.cms_id)
                .filter(StudentProgram.id == student_program_id)
                .first()
            )
            if result and result[0]:
                return result[0]
            return None

    def get_structure_by_id(self, structure_id: int) -> Optional[StructureOption]:
        with self._session() as session:
            result = (
                session.query(
                    Structure.id.label("db_id"),
                    Structure.cms_id.label("cms_id"),
                    Structure.code,
                    Structure.desc,
                )
                .filter(Structure.id == structure_id)
                .first()
            )

            if not result or result.cms_id is None:
                return None

            return StructureOption(
                db_id=result.db_id,
                cms_id=result.cms_id,
                code=result.code,
                desc=result.desc,
            )
