from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import String, distinct, or_
from sqlalchemy.orm import Session

from base import get_logger
from database import (
    Clearance,
    Module,
    Program,
    RegistrationClearance,
    RegistrationRequest,
    RequestedModule,
    School,
    SemesterModule,
    Sponsor,
    SponsoredStudent,
    Student,
    Term,
    get_engine,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class RegistrationRequestRow:
    id: int
    std_no: str
    student_name: Optional[str]
    sponsor_name: Optional[str]
    term_code: Optional[str]
    semester_number: str
    semester_status: str
    status: str
    school_name: Optional[str]
    program_name: Optional[str]
    module_count: int
    created_at: Optional[str]


class EnrollmentRequestRepository:
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
            rows = session.query(Term.id, Term.code).order_by(Term.code.desc()).all()
            return rows

    def list_statuses(self):
        return [
            ("approved", "Approved"),
            ("pending", "Pending"),
            ("rejected", "Rejected"),
            ("registered", "Registered"),
        ]

    def fetch_registration_requests(
        self,
        *,
        school_id: Optional[int] = None,
        program_id: Optional[int] = None,
        term_id: Optional[int] = None,
        status: Optional[str] = None,
        search_query: str = "",
        page: int = 1,
        page_size: int = 30,
    ):
        offset = (page - 1) * page_size
        with self._session() as session:
            from database import Structure, StudentProgram

            base_query = (
                session.query(
                    RegistrationRequest.id,
                    Student.std_no,
                    Student.name.label("student_name"),
                    Sponsor.name.label("sponsor_name"),
                    Term.code.label("term_code"),
                    RegistrationRequest.semester_number,
                    RegistrationRequest.semester_status,
                    RegistrationRequest.status,
                    School.name.label("school_name"),
                    Program.name.label("program_name"),
                    RegistrationRequest.created_at,
                )
                .join(Student, RegistrationRequest.std_no == Student.std_no)
                .join(
                    SponsoredStudent,
                    RegistrationRequest.sponsored_student_id == SponsoredStudent.id,
                )
                .join(Sponsor, SponsoredStudent.sponsor_id == Sponsor.id)
                .join(Term, RegistrationRequest.term_id == Term.id)
                .outerjoin(
                    StudentProgram,
                    (Student.std_no == StudentProgram.std_no)
                    & (StudentProgram.status == "Active"),
                )
                .outerjoin(Structure, StudentProgram.structure_id == Structure.id)
                .outerjoin(Program, Structure.program_id == Program.id)
                .outerjoin(School, Program.school_id == School.id)
            )

            if school_id:
                base_query = base_query.filter(School.id == school_id)

            if program_id:
                base_query = base_query.filter(Program.id == program_id)

            if term_id:
                base_query = base_query.filter(Term.id == term_id)

            if search_query:
                search_term = f"%{search_query}%"
                base_query = base_query.filter(
                    or_(
                        Student.std_no.cast(String).like(search_term),
                        Student.name.like(search_term),
                        Sponsor.name.like(search_term),
                    )
                )

            if status:
                from sqlalchemy import and_, not_

                if status == "pending":
                    base_query = base_query.filter(
                        RegistrationRequest.status == "pending"
                    )
                elif status == "approved":
                    approved_exists = (
                        session.query(RegistrationClearance)
                        .join(
                            Clearance,
                            RegistrationClearance.clearance_id == Clearance.id,
                        )
                        .filter(
                            RegistrationClearance.registration_request_id
                            == RegistrationRequest.id,
                            Clearance.status == "approved",
                        )
                        .exists()
                    )
                    nonapproved_exists = (
                        session.query(RegistrationClearance)
                        .join(
                            Clearance,
                            RegistrationClearance.clearance_id == Clearance.id,
                        )
                        .filter(
                            RegistrationClearance.registration_request_id
                            == RegistrationRequest.id,
                            Clearance.status != "approved",
                        )
                        .exists()
                    )
                    base_query = base_query.filter(
                        and_(
                            RegistrationRequest.status == "pending",
                            approved_exists,
                            not_(nonapproved_exists),
                        )
                    )
                elif status == "rejected":
                    rejected_subquery = (
                        session.query(RegistrationClearance)
                        .join(
                            Clearance,
                            RegistrationClearance.clearance_id == Clearance.id,
                        )
                        .filter(
                            RegistrationClearance.registration_request_id
                            == RegistrationRequest.id,
                            Clearance.status == "rejected",
                        )
                        .exists()
                    )
                    base_query = base_query.filter(rejected_subquery)
                elif status == "registered":
                    base_query = base_query.filter(
                        RegistrationRequest.status == "registered"
                    )

            base_query = base_query.order_by(RegistrationRequest.created_at.desc())
            total = base_query.count()
            results = base_query.offset(offset).limit(page_size).all()

        rows = []
        for result in results:
            module_count = self._get_module_count(result.id)
            rows.append(
                RegistrationRequestRow(
                    id=result.id,
                    std_no=str(result.std_no),
                    student_name=result.student_name,
                    sponsor_name=result.sponsor_name,
                    term_code=result.term_code,
                    semester_number=result.semester_number,
                    semester_status=result.semester_status,
                    status=result.status,
                    school_name=result.school_name,
                    program_name=result.program_name,
                    module_count=module_count,
                    created_at=result.created_at,
                )
            )

        return rows, total

    def _get_module_count(self, registration_request_id: int) -> int:
        with self._session() as session:
            count = (
                session.query(RequestedModule)
                .filter(
                    RequestedModule.registration_request_id == registration_request_id
                )
                .count()
            )
            return count

    def get_registration_request_details(self, registration_request_id: int):
        with self._session() as session:
            request = (
                session.query(
                    RegistrationRequest.id,
                    Student.std_no,
                    Student.name.label("student_name"),
                    Sponsor.name.label("sponsor_name"),
                    Term.code.label("term_code"),
                    RegistrationRequest.semester_number,
                    RegistrationRequest.semester_status,
                    RegistrationRequest.status,
                    RegistrationRequest.message,
                    RegistrationRequest.created_at,
                    RegistrationRequest.date_approved,
                )
                .join(Student, RegistrationRequest.std_no == Student.std_no)
                .join(
                    SponsoredStudent,
                    RegistrationRequest.sponsored_student_id == SponsoredStudent.id,
                )
                .join(Sponsor, SponsoredStudent.sponsor_id == Sponsor.id)
                .join(Term, RegistrationRequest.term_id == Term.id)
                .filter(RegistrationRequest.id == registration_request_id)
                .first()
            )

            if not request:
                return None

            return {
                "id": request.id,
                "std_no": request.std_no,
                "student_name": request.student_name,
                "sponsor_name": request.sponsor_name,
                "term_code": request.term_code,
                "semester_number": request.semester_number,
                "semester_status": request.semester_status,
                "status": request.status,
                "message": request.message,
                "created_at": request.created_at,
                "date_approved": request.date_approved,
            }

    def get_enrollment_data(self, registration_request_id: int):
        with self._session() as session:
            from database import Structure, StudentProgram

            result = (
                session.query(
                    RegistrationRequest.id.label("request_id"),
                    Student.std_no,
                    Term.code.label("term_code"),
                    RegistrationRequest.semester_number,
                    RegistrationRequest.semester_status,
                    StudentProgram.id.label("student_program_id"),
                    StudentProgram.structure_id,
                )
                .join(Student, RegistrationRequest.std_no == Student.std_no)
                .join(Term, RegistrationRequest.term_id == Term.id)
                .outerjoin(
                    StudentProgram,
                    (StudentProgram.std_no == Student.std_no)
                    & (StudentProgram.status == "Active"),
                )
                .filter(RegistrationRequest.id == registration_request_id)
                .first()
            )

            if not result:
                return None

            modules = (
                session.query(
                    Module.code.label("module_code"),
                    RequestedModule.module_status,
                    RequestedModule.semester_module_id,
                    SemesterModule.credits,
                )
                .join(
                    SemesterModule,
                    RequestedModule.semester_module_id == SemesterModule.id,
                )
                .join(Module, SemesterModule.module_id == Module.id)
                .filter(
                    RequestedModule.registration_request_id == registration_request_id
                )
                .order_by(Module.code)
                .all()
            )

            return {
                "request_id": result.request_id,
                "std_no": result.std_no,
                "term_code": result.term_code,
                "semester_number": result.semester_number,
                "semester_status": result.semester_status,
                "student_program_id": result.student_program_id,
                "structure_id": result.structure_id,
                "modules": modules,
            }

    def get_requested_modules(self, registration_request_id: int):
        with self._session() as session:
            modules = (
                session.query(
                    RequestedModule.id,
                    Module.code.label("module_code"),
                    Module.name.label("module_name"),
                    RequestedModule.module_status,
                    RequestedModule.status,
                    SemesterModule.credits,
                    RequestedModule.semester_module_id,
                )
                .join(
                    SemesterModule,
                    RequestedModule.semester_module_id == SemesterModule.id,
                )
                .join(Module, SemesterModule.module_id == Module.id)
                .filter(
                    RequestedModule.registration_request_id == registration_request_id
                )
                .order_by(Module.code)
                .all()
            )
            return modules

    def get_active_student_program(self, std_no: int):
        with self._session() as session:
            from database import Structure, StudentProgram

            program = (
                session.query(
                    StudentProgram.id,
                    StudentProgram.structure_id,
                    StudentProgram.std_no,
                )
                .filter(StudentProgram.std_no == std_no)
                .filter(StudentProgram.status == "Active")
                .first()
            )

            if not program:
                return None

            return {
                "id": program.id,
                "structure_id": program.structure_id,
                "std_no": program.std_no,
            }

    def get_structure_semester_by_number(self, structure_id: int, semester_number: str):
        with self._session() as session:
            from database import StructureSemester

            semester = (
                session.query(StructureSemester.id)
                .filter(StructureSemester.structure_id == structure_id)
                .filter(StructureSemester.semester_number == semester_number)
                .first()
            )

            if not semester:
                return None

            return semester[0]

    def upsert_student_semester(self, student_program_id: int, data: dict) -> bool:
        with self._session() as session:
            from database import StudentSemester

            try:
                semester_id = data.get("id")

                if semester_id:
                    existing = (
                        session.query(StudentSemester)
                        .filter(StudentSemester.id == semester_id)
                        .first()
                    )

                    if not existing:
                        existing = (
                            session.query(StudentSemester)
                            .filter(
                                StudentSemester.student_program_id == student_program_id
                            )
                            .filter(StudentSemester.term_code == data.get("term"))
                            .first()
                        )

                    if existing:
                        if "structure_semester_id" in data:
                            existing.structure_semester_id = data[
                                "structure_semester_id"
                            ]
                        if "status" in data:
                            existing.status = data["status"]
                        if "caf_date" in data:
                            existing.caf_date = data["caf_date"]
                        if "sponsor_id" in data:
                            existing.sponsor_id = data["sponsor_id"]
                        if "registration_request_id" in data:
                            existing.registration_request_id = data[
                                "registration_request_id"
                            ]

                        session.commit()
                        logger.info(f"Updated student semester {semester_id}")
                        return True
                    else:
                        if (
                            "structure_semester_id" not in data
                            or not data["structure_semester_id"]
                        ):
                            logger.error(
                                f"Cannot create student semester without structure_semester_id - "
                                f"student_program_id={student_program_id}, data={data}"
                            )
                            return False

                        new_semester = StudentSemester(
                            id=semester_id,
                            student_program_id=student_program_id,
                            term=data.get("term"),
                            structure_semester_id=data["structure_semester_id"],
                            status=data.get("status", "Active"),
                            caf_date=data.get("caf_date"),
                            sponsor_id=data.get("sponsor_id"),
                            registration_request_id=data.get("registration_request_id"),
                        )
                        session.add(new_semester)
                        session.commit()
                        logger.info(f"Created student semester {semester_id}")
                        return True
                else:
                    logger.error("Cannot create student semester without ID from CMS")
                    return False

            except Exception as e:
                session.rollback()
                logger.error(f"Error upserting student semester: {str(e)}")
                return False

    def upsert_student_module(self, data: dict) -> bool:
        with self._session() as session:
            from database import StudentModule

            try:
                module_id = data.get("id")
                if not module_id:
                    logger.error("Cannot create student module without ID")
                    return False

                existing = (
                    session.query(StudentModule)
                    .filter(StudentModule.id == module_id)
                    .first()
                )

                if existing:
                    if "semester_module_id" in data:
                        existing.semester_module_id = data["semester_module_id"]
                    if "status" in data:
                        existing.status = data["status"]
                    if "credits" in data:
                        existing.credits = float(data["credits"])
                    if "marks" in data:
                        existing.marks = data["marks"]
                    if "grade" in data:
                        existing.grade = data["grade"]
                    if "student_semester_id" in data:
                        existing.student_semester_id = data["student_semester_id"]

                    session.commit()
                    logger.info(f"Updated student module {module_id}")
                    return True
                else:
                    new_module = StudentModule(
                        id=module_id,
                        semester_module_id=data.get("semester_module_id"),
                        status=data.get("status", ""),
                        credits=float(data.get("credits", 0)),
                        marks=data.get("marks", "NM"),
                        grade=data.get("grade", "NM"),
                        student_semester_id=data.get("student_semester_id"),
                    )
                    session.add(new_module)
                    session.commit()
                    logger.info(f"Created student module {module_id}")
                    return True

            except Exception as e:
                session.rollback()
                logger.error(f"Error upserting student module: {str(e)}")
                return False

    def update_registration_request_status(self, request_id: int, status: str) -> bool:
        with self._session() as session:
            try:
                request = (
                    session.query(RegistrationRequest)
                    .filter(RegistrationRequest.id == request_id)
                    .first()
                )

                if not request:
                    logger.error(f"Registration request {request_id} not found")
                    return False

                request.status = status  # type: ignore
                if status == "registered":
                    request.date_registered = datetime.now()  # type: ignore
                session.commit()
                logger.info(
                    f"Updated registration request {request_id} status to {status}"
                )
                return True

            except Exception as e:
                session.rollback()
                logger.error(f"Error updating registration request status: {str(e)}")
                return False

    def get_clearances_for_request(self, registration_request_id: int):
        with self._session() as session:
            clearances = (
                session.query(
                    Clearance.id,
                    Clearance.department,
                    Clearance.status,
                    Clearance.message,
                    Clearance.responded_by,
                    Clearance.response_date,
                )
                .join(
                    RegistrationClearance,
                    RegistrationClearance.clearance_id == Clearance.id,
                )
                .filter(
                    RegistrationClearance.registration_request_id
                    == registration_request_id
                )
                .order_by(Clearance.department)
                .all()
            )
            return clearances
