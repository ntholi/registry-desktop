from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import distinct, or_
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
    term_name: Optional[str]
    semester_number: int
    semester_status: str
    status: str
    school_name: Optional[str]
    program_name: Optional[str]
    module_count: int
    created_at: Optional[str]


class ApprovedEnrollmentRepository:
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
            rows = session.query(Term.id, Term.name).order_by(Term.name.desc()).all()
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
        statuses: Optional[set[str]] = None,
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
                    Term.name.label("term_name"),
                    RegistrationRequest.semester_number,
                    RegistrationRequest.semester_status,
                    RegistrationRequest.status,
                    School.name.label("school_name"),
                    Program.name.label("program_name"),
                    RegistrationRequest.created_at,
                )
                .join(Student, RegistrationRequest.std_no == Student.std_no)
                .join(Sponsor, RegistrationRequest.sponsor_id == Sponsor.id)
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
                        Student.std_no.like(search_term),
                        Student.name.like(search_term),
                        Sponsor.name.like(search_term),
                    )
                )

            if statuses:
                from sqlalchemy import and_, exists, not_

                conditions = []
                for status in statuses:
                    if status == "pending":
                        conditions.append(RegistrationRequest.status == "pending")
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
                        approved_subquery = and_(
                            RegistrationRequest.status == "pending",
                            approved_exists,
                            not_(nonapproved_exists),
                        )
                        conditions.append(approved_subquery)
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
                        conditions.append(rejected_subquery)
                    elif status == "registered":
                        conditions.append(RegistrationRequest.status == "registered")

                if conditions:
                    base_query = base_query.filter(or_(*conditions))

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
                    term_name=result.term_name,
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
                    Term.name.label("term_name"),
                    RegistrationRequest.semester_number,
                    RegistrationRequest.semester_status,
                    RegistrationRequest.status,
                    RegistrationRequest.message,
                    RegistrationRequest.created_at,
                    RegistrationRequest.date_approved,
                )
                .join(Student, RegistrationRequest.std_no == Student.std_no)
                .join(Sponsor, RegistrationRequest.sponsor_id == Sponsor.id)
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
                "term_name": request.term_name,
                "semester_number": request.semester_number,
                "semester_status": request.semester_status,
                "status": request.status,
                "message": request.message,
                "created_at": request.created_at,
                "date_approved": request.date_approved,
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
