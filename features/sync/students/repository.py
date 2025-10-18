from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import distinct, or_
from sqlalchemy.orm import Session

from database import (
    Program,
    School,
    Structure,
    Student,
    StudentProgram,
    StudentSemester,
    get_engine,
)


@dataclass(frozen=True)
class StudentRow:
    std_no: str
    name: Optional[str]
    gender: Optional[str]
    faculty_code: Optional[str]
    program_name: Optional[str]


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
                    School.code.label("faculty_code"),
                    Program.name.label("program_name"),
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
                faculty_code=result.faculty_code,
                program_name=result.program_name,
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
                return False

            for key, value in data.items():
                if value is None or not hasattr(student, key):
                    continue
                setattr(student, key, value)

            session.commit()
            return True
