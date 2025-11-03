from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, cast

from sqlalchemy import String, distinct, or_
from sqlalchemy.orm import Session

from base import get_logger
from database import (
    Module,
    NextOfKin,
    Program,
    School,
    SemesterModule,
    Structure,
    Student,
    StudentEducation,
    StudentModule,
    StudentProgram,
    StudentSemester,
    get_engine,
)
from database.models import StudentModuleStatus

logger = get_logger(__name__)


VALID_STUDENT_MODULE_STATUSES = set(StudentModuleStatus.__args__)
STATUS_ALIASES: dict[str, str] = {
    "ACTIVE": "Compulsory",
}
DEFAULT_STUDENT_MODULE_STATUS = "Compulsory"


def normalize_student_module_status(status: str | None) -> str:
    if not status:
        return DEFAULT_STUDENT_MODULE_STATUS

    candidate = status.strip()
    if not candidate:
        return DEFAULT_STUDENT_MODULE_STATUS

    if candidate in VALID_STUDENT_MODULE_STATUSES:
        return candidate

    upper_candidate = candidate.upper()
    if upper_candidate in STATUS_ALIASES:
        return STATUS_ALIASES[upper_candidate]

    if candidate.lower().startswith("repeat"):
        suffix = candidate[6:]
        try:
            repeat_number = int(suffix)
        except ValueError:
            repeat_number = None

        if repeat_number is not None and 1 <= repeat_number <= 7:
            return f"Repeat{repeat_number}"
        return "Repeat1"

    return DEFAULT_STUDENT_MODULE_STATUS


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
                        Student.std_no.cast(String).like(search_term),
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

    def get_student_programs(self, student_number: str):
        try:
            numeric_student_number = int(student_number)
        except (TypeError, ValueError):
            return []

        with self._session() as session:
            programs = (
                session.query(
                    StudentProgram.id,
                    StudentProgram.intake_date,
                    StudentProgram.reg_date,
                    StudentProgram.start_term,
                    StudentProgram.status,
                    StudentProgram.stream,
                    StudentProgram.graduation_date,
                    Program.name.label("program_name"),
                    Program.code.label("program_code"),
                    School.name.label("school_name"),
                )
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .join(Program, Structure.program_id == Program.id)
                .join(School, Program.school_id == School.id)
                .filter(StudentProgram.std_no == numeric_student_number)
                .order_by(StudentProgram.id.desc())
                .all()
            )

            return programs

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

    def get_student_program_details_by_id(self, student_program_id: int):
        with self._session() as session:
            program_details = (
                session.query(
                    StudentProgram.std_no,
                    StudentProgram.intake_date,
                    StudentProgram.start_term,
                    Structure.id.label("structure_id"),
                    Program.id.label("program_id"),
                    School.id.label("school_id"),
                )
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .join(Program, Structure.program_id == Program.id)
                .join(School, Program.school_id == School.id)
                .filter(StudentProgram.id == student_program_id)
                .first()
            )

            if not program_details:
                return None

            return {
                "std_no": program_details.std_no,
                "intake_date": program_details.intake_date,
                "start_term": program_details.start_term,
                "structure_id": program_details.structure_id,
                "program_id": program_details.program_id,
                "school_id": program_details.school_id,
            }

    def get_structure_semesters(self, structure_id: int):
        with self._session() as session:
            from database import StructureSemester

            semesters = (
                session.query(
                    StructureSemester.id,
                    StructureSemester.semester_number,
                    StructureSemester.name,
                )
                .filter(StructureSemester.structure_id == structure_id)
                .order_by(StructureSemester.semester_number)
                .all()
            )
            return semesters

    def get_structure_semester_number(self, structure_semester_id: int):
        with self._session() as session:
            from database import StructureSemester

            semester = (
                session.query(StructureSemester.semester_number)
                .filter(StructureSemester.id == structure_semester_id)
                .first()
            )
            return semester[0] if semester else None

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
                    status=data.get("status") or "Active",
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

    def get_student_semesters(self, student_program_id: int):
        with self._session() as session:
            semesters = (
                session.query(
                    StudentSemester.id,
                    StudentSemester.term,
                    StudentSemester.semester_number,
                    StudentSemester.status,
                    StudentSemester.caf_date,
                )
                .filter(StudentSemester.student_program_id == student_program_id)
                .order_by(StudentSemester.term, StudentSemester.semester_number)
                .all()
            )
            return semesters

    def get_student_semester_by_id(self, student_semester_id: int):
        with self._session() as session:
            result = (
                session.query(
                    StudentSemester.id,
                    StudentSemester.student_program_id,
                    StudentSemester.term,
                    StudentSemester.semester_number,
                    StudentSemester.status,
                    StudentSemester.caf_date,
                    StudentProgram.structure_id,
                )
                .join(
                    StudentProgram,
                    StudentSemester.student_program_id == StudentProgram.id,
                )
                .filter(StudentSemester.id == student_semester_id)
                .first()
            )
            if result:
                return {
                    "id": result[0],
                    "student_program_id": result[1],
                    "term": result[2],
                    "semester_number": result[3],
                    "status": result[4],
                    "caf_date": result[5],
                    "structure_id": result[6],
                }
            return None

    def get_semester_modules(self, student_semester_id: int):
        with self._session() as session:
            modules = (
                session.query(
                    StudentModule.id,
                    Module.code.label("module_code"),
                    Module.name.label("module_name"),
                    StudentModule.status,
                    StudentModule.marks,
                    StudentModule.grade,
                    SemesterModule.credits,
                )
                .join(
                    SemesterModule,
                    StudentModule.semester_module_id == SemesterModule.id,
                )
                .join(Module, SemesterModule.module_id == Module.id)
                .filter(StudentModule.student_semester_id == student_semester_id)
                .order_by(Module.code)
                .all()
            )
            return modules

    def search_semester_modules(self, search_query: str):
        with self._session() as session:
            from database import StructureSemester

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

    def upsert_student_program(
        self, student_program_id: str, std_no: int, data: dict
    ) -> tuple[bool, str]:
        with self._session() as session:
            try:
                existing = (
                    session.query(StudentProgram)
                    .filter(StudentProgram.std_no == std_no)
                    .filter(StudentProgram.id == int(student_program_id))
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
                        f"Updated student program {student_program_id} for student {std_no}"
                    )
                    return True, "Student program updated"
                else:
                    if not structure_id:
                        logger.error(
                            f"Cannot create student program without valid structure"
                        )
                        return False, "Structure not found"

                    new_program = StudentProgram(
                        id=int(student_program_id),
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
                        f"Created student program {student_program_id} for student {std_no}"
                    )
                    return True, "Student program created"

            except Exception as e:
                session.rollback()
                error_msg = f"Error upserting student program: {str(e)}"
                logger.error(error_msg)
                return False, error_msg

    def upsert_student_semester(
        self, std_program_id: int, data: dict
    ) -> tuple[bool, str, Optional[int]]:
        with self._session() as session:
            try:
                semester_id = None
                if "id" in data:
                    try:
                        semester_id = int(data["id"])
                    except (TypeError, ValueError):
                        logger.warning(f"Invalid semester ID: {data.get('id')}")

                existing = None
                if semester_id:
                    existing = (
                        session.query(StudentSemester)
                        .filter(StudentSemester.id == semester_id)
                        .first()
                    )

                if not existing:
                    existing = (
                        session.query(StudentSemester)
                        .filter(StudentSemester.student_program_id == std_program_id)
                        .filter(StudentSemester.term == data.get("term"))
                        .first()
                    )

                if existing:
                    if "semester_number" in data:
                        existing.semester_number = data["semester_number"]
                    if "status" in data:
                        existing.status = data["status"]
                    if "semester_status" in data:
                        existing.status = data["semester_status"]
                    if "caf_date" in data:
                        existing.caf_date = data["caf_date"]

                    session.commit()
                    logger.info(
                        f"Updated student semester {existing.id} for program {std_program_id}"
                    )
                    return True, "Student semester updated", cast(int, existing.id)
                else:
                    if not semester_id:
                        error_msg = "Cannot create student semester without ID from CMS"
                        logger.error(error_msg)
                        return False, error_msg, None

                    new_semester = StudentSemester(
                        id=semester_id,
                        student_program_id=std_program_id,
                        term=data.get("term"),
                        semester_number=data.get("semester_number"),
                        status=data.get("status")
                        or data.get("semester_status", "Active"),
                        caf_date=data.get("caf_date"),
                    )
                    session.add(new_semester)
                    session.commit()
                    logger.info(
                        f"Created student semester {semester_id} for program {std_program_id}"
                    )
                    return True, "Student semester created", semester_id

            except Exception as e:
                session.rollback()
                error_msg = f"Error upserting student semester: {str(e)}"
                logger.error(error_msg)
                return False, error_msg, None

    def get_semester_module_by_code(
        self, module_code: str, structure_id: int
    ) -> Optional[int]:
        with self._session() as session:
            semester_module = (
                session.query(SemesterModule.id)
                .join(Module, SemesterModule.module_id == Module.id)
                .join(Structure, Structure.id == structure_id)
                .filter(Module.code == module_code)
                .first()
            )
            return semester_module[0] if semester_module else None

    def get_semester_module_credits(self, semester_module_id: int) -> Optional[float]:
        with self._session() as session:
            semester_module = (
                session.query(SemesterModule.credits)
                .filter(SemesterModule.id == semester_module_id)
                .first()
            )
            return semester_module[0] if semester_module else None

    def upsert_student_module(self, data: dict) -> tuple[bool, str]:
        with self._session() as session:
            try:
                std_module_id = int(data["id"])
                student_semester_id = data.get("student_semester_id")

                if not student_semester_id:
                    return False, "Missing student_semester_id"

                existing = (
                    session.query(StudentModule)
                    .filter(StudentModule.id == std_module_id)
                    .first()
                )

                semester_module_id = None

                if "semester_module_id" in data and data["semester_module_id"]:
                    semester_module_id = data["semester_module_id"]
                elif "module_code" in data:
                    student_semester = (
                        session.query(StudentSemester)
                        .filter(StudentSemester.id == student_semester_id)
                        .first()
                    )

                    if student_semester is not None:
                        student_program_id = cast(
                            int, student_semester.student_program_id
                        )
                        student_program = (
                            session.query(StudentProgram)
                            .filter(StudentProgram.id == student_program_id)
                            .first()
                        )

                        if student_program is not None:
                            structure_id = cast(int, student_program.structure_id)
                            semester_module_id = self.get_semester_module_by_code(
                                data["module_code"], structure_id
                            )

                            if not semester_module_id:
                                logger.warning(
                                    f"Semester module not found for code {data['module_code']}"
                                )

                if existing:
                    if semester_module_id:
                        existing.semester_module_id = semester_module_id  # type: ignore
                    if "status" in data:
                        existing.status = normalize_student_module_status(
                            data["status"]
                        )
                    if "marks" in data:
                        existing.marks = data["marks"]
                    if "grade" in data:
                        existing.grade = data["grade"]
                    if "student_semester_id" in data:
                        existing.student_semester_id = data["student_semester_id"]

                    session.commit()
                    logger.info(f"Updated student module {std_module_id}")
                    return True, "Student module updated"
                else:
                    if not semester_module_id:
                        logger.warning(
                            f"Creating student module {std_module_id} without semester_module_id"
                        )

                    new_module = StudentModule(
                        id=std_module_id,
                        semester_module_id=semester_module_id or 0,
                        status=normalize_student_module_status(data.get("status")),
                        marks=data.get("marks", "NM"),
                        grade=data.get("grade", "NM"),
                        student_semester_id=student_semester_id,
                    )
                    session.add(new_module)
                    session.commit()
                    logger.info(f"Created student module {std_module_id}")
                    return True, "Student module created"

            except Exception as e:
                session.rollback()
                error_msg = f"Error upserting student module: {str(e)}"
                logger.error(error_msg)
                return False, error_msg

    def upsert_next_of_kin(
        self, student_number: str, next_of_kin_list: list[dict]
    ) -> tuple[bool, str]:
        try:
            numeric_student_number = int(student_number)
        except (TypeError, ValueError):
            return False, "Invalid student number"

        with self._session() as session:
            try:
                existing_kin = (
                    session.query(NextOfKin)
                    .filter(NextOfKin.std_no == numeric_student_number)
                    .all()
                )

                existing_map = {
                    (kin.relationship, kin.name): kin for kin in existing_kin
                }

                for kin_data in next_of_kin_list:
                    name = kin_data.get("name")
                    relationship = kin_data.get("relationship")

                    if not name or not relationship:
                        continue

                    key = (relationship, name)

                    if key in existing_map:
                        existing = existing_map[key]
                        if kin_data.get("phone"):
                            existing.phone = kin_data["phone"]
                        if kin_data.get("email"):
                            existing.email = kin_data["email"]
                    else:
                        new_kin = NextOfKin(
                            std_no=numeric_student_number,
                            name=name,
                            relationship=relationship,
                            phone=kin_data.get("phone"),
                            email=kin_data.get("email"),
                        )
                        session.add(new_kin)

                session.commit()
                logger.info(f"Updated next of kin records for student {student_number}")
                return True, "Next of kin records updated"

            except Exception as e:
                session.rollback()
                error_msg = f"Error upserting next of kin: {str(e)}"
                logger.error(error_msg)
                return False, error_msg

    def upsert_student_education(self, data: dict) -> tuple[bool, str]:
        with self._session() as session:
            try:
                education_id = int(data["id"])
                std_no = data.get("std_no")

                if not std_no:
                    return False, "Missing student number"

                existing = (
                    session.query(StudentEducation)
                    .filter(StudentEducation.id == education_id)
                    .first()
                )

                if existing:
                    if "school_name" in data:
                        existing.school_name = data["school_name"]
                    if "type" in data:
                        existing.type = data["type"]
                    if "level" in data:
                        existing.level = data["level"]
                    if "start_date" in data:
                        existing.start_date = data["start_date"]
                    if "end_date" in data:
                        existing.end_date = data["end_date"]

                    session.commit()
                    logger.info(f"Updated student education {education_id}")
                    return True, "Student education updated"
                else:
                    new_education = StudentEducation(
                        id=education_id,
                        std_no=std_no,
                        school_name=data.get("school_name", ""),
                        type=data.get("type"),
                        level=data.get("level"),
                        start_date=data.get("start_date"),
                        end_date=data.get("end_date"),
                    )
                    session.add(new_education)
                    session.commit()
                    logger.info(f"Created student education {education_id}")
                    return True, "Student education created"

            except Exception as e:
                session.rollback()
                error_msg = f"Error upserting student education: {str(e)}"
                logger.error(error_msg)
                return False, error_msg
