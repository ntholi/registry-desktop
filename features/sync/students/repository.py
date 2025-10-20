from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import distinct, or_
from sqlalchemy.orm import Session

from base import get_logger
from database import (
    Program,
    School,
    Structure,
    Student,
    StudentProgram,
    StudentSemester,
    get_engine,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class StudentRow:
    std_no: str
    name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[str]
    faculty_code: Optional[str]
    program_name: Optional[str]
    phone1: Optional[str]


class StudentRepository:
    def __init__(self) -> None:
        self._engine = get_engine(use_local=True)

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

    def list_terms(self):
        with self._session() as session:
            rows = (
                session.query(distinct(StudentSemester.term))
                .filter(StudentSemester.term.isnot(None))
                .order_by(StudentSemester.term.desc())
                .all()
            )
            return [row[0] for row in rows]

    def list_semesters(self):
        with self._session() as session:
            rows = (
                session.query(distinct(StudentSemester.semester_number))
                .filter(StudentSemester.semester_number.isnot(None))
                .order_by(StudentSemester.semester_number)
                .all()
            )
            return [row[0] for row in rows]

    def fetch_students(
        self,
        *,
        school_id: Optional[int] = None,
        program_id: Optional[int] = None,
        term: Optional[str] = None,
        semester_number: Optional[int] = None,
        search_query: str = "",
        page: int = 1,
        page_size: int = 30,
    ):
        offset = (page - 1) * page_size
        with self._session() as session:
            query = (
                session.query(
                    Student.std_no,
                    Student.name,
                    Student.gender,
                    Student.date_of_birth,
                    School.code.label("faculty_code"),
                    Program.name.label("program_name"),
                    Student.phone1,
                )
                .outerjoin(
                    StudentProgram,
                    (Student.std_no == StudentProgram.std_no)
                    & (StudentProgram.status == "Active"),
                )
                .outerjoin(Structure, StudentProgram.structure_id == Structure.id)
                .outerjoin(Program, Structure.program_id == Program.id)
                .outerjoin(School, Program.school_id == School.id)
                .distinct()
            )

            if school_id:
                query = query.filter(Program.school_id == school_id)

            if program_id:
                query = query.filter(Program.id == program_id)

            if term or semester_number:
                query = query.join(
                    StudentSemester,
                    StudentProgram.id == StudentSemester.student_program_id,
                )
                if term:
                    query = query.filter(StudentSemester.term == term)
                if semester_number:
                    query = query.filter(
                        StudentSemester.semester_number == semester_number
                    )

            if search_query:
                search_term = f"%{search_query}%"
                query = query.filter(
                    or_(
                        Student.std_no.like(search_term),
                        Student.name.like(search_term),
                        Student.national_id.like(search_term),
                    )
                )

            query = query.order_by(Student.std_no.desc())
            total = query.count()
            results = query.offset(offset).limit(page_size).all()

        rows = [
            StudentRow(
                std_no=str(result.std_no),
                name=result.name,
                gender=result.gender,
                date_of_birth=result.date_of_birth,
                faculty_code=result.faculty_code,
                program_name=result.program_name,
                phone1=result.phone1,
            )
            for result in results
        ]
        return rows, total

    def get_student_program_details(self, student_number: str):
        try:
            numeric_student_number = int(student_number)
        except (TypeError, ValueError):
            return None

        with self._session() as session:
            program_details = (
                session.query(
                    StudentProgram.intake_date,
                    StudentProgram.start_term,
                    Structure.id.label("structure_id"),
                    Program.id.label("program_id"),
                    School.id.label("school_id"),
                )
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .join(Program, Structure.program_id == Program.id)
                .join(School, Program.school_id == School.id)
                .filter(StudentProgram.std_no == numeric_student_number)
                .filter(
                    or_(
                        StudentProgram.status == "Active",
                        StudentProgram.status == "Completed",
                    )
                )
                .order_by(StudentProgram.id)
                .first()
            )

            if not program_details:
                return None

            return {
                "intake_date": program_details.intake_date,
                "start_term": program_details.start_term,
                "structure_id": program_details.structure_id,
                "program_id": program_details.program_id,
                "school_id": program_details.school_id,
            }

    def update_student(self, student_number: str, data: dict):
        try:
            numeric_student_number = int(student_number)
        except (TypeError, ValueError):
            return False

        with self._session() as session:
            student = (
                session.query(Student)
                .filter(Student.std_no == numeric_student_number)
                .first()
            )

            if not student:
                student = Student(
                    std_no=numeric_student_number,
                    name=data.get("name") or "",
                    national_id=data.get("national_id") or "",
                    sem=data.get("sem") or 0,
                )
                session.add(student)

            for key, value in data.items():
                if value is None or not hasattr(student, key):
                    continue
                setattr(student, key, value)

            session.commit()
            return True

    def get_structure_by_code(self, structure_code: str) -> Optional[int]:
        with self._session() as session:
            structure = (
                session.query(Structure.id)
                .filter(Structure.code == structure_code)
                .first()
            )
            return structure[0] if structure else None

    def upsert_student_program(
        self, cms_id: str, std_no: int, data: dict
    ) -> tuple[bool, str]:
        with self._session() as session:
            try:
                existing = (
                    session.query(StudentProgram)
                    .filter(StudentProgram.std_no == std_no)
                    .filter(StudentProgram.id == int(cms_id))
                    .first()
                )

                structure_id = None
                if "structure_code" in data:
                    structure_id = self.get_structure_by_code(data["structure_code"])
                    if not structure_id:
                        logger.warning(
                            f"Structure {data['structure_code']} not found in database"
                        )

                if existing:
                    if structure_id:
                        existing.structure_id = structure_id  # type: ignore
                    if "reg_date" in data:
                        existing.reg_date = data["reg_date"]
                    if "intake_date" in data:
                        existing.intake_date = data["intake_date"]
                    if "start_term" in data:
                        existing.start_term = data["start_term"]
                    if "stream" in data:
                        existing.stream = data["stream"]
                    if "status" in data:
                        existing.status = data["status"]
                    if "assist_provider" in data:
                        existing.assist_provider = data["assist_provider"]
                    if "graduation_date" in data:
                        existing.graduation_date = data["graduation_date"]

                    session.commit()
                    logger.info(
                        f"Updated student program {cms_id} for student {std_no}"
                    )
                    return True, "Student program updated"
                else:
                    if not structure_id:
                        logger.error(
                            f"Cannot create student program without valid structure"
                        )
                        return False, "Structure not found"

                    new_program = StudentProgram(
                        id=int(cms_id),
                        std_no=std_no,
                        structure_id=structure_id,
                        reg_date=data.get("reg_date"),
                        intake_date=data.get("intake_date"),
                        start_term=data.get("start_term"),
                        stream=data.get("stream"),
                        status=data.get("status", "Active"),
                        assist_provider=data.get("assist_provider"),
                        graduation_date=data.get("graduation_date"),
                    )
                    session.add(new_program)
                    session.commit()
                    logger.info(
                        f"Created student program {cms_id} for student {std_no}"
                    )
                    return True, "Student program created"

            except Exception as e:
                session.rollback()
                error_msg = f"Error upserting student program: {str(e)}"
                logger.error(error_msg)
                return False, error_msg
