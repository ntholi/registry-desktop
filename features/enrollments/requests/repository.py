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
    request_db_id: int
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

    def list_terms(self):
        with self._session() as session:
            rows = (
                session.query(distinct(Term.code).label("code"))
                .order_by(Term.code.desc())
                .all()
            )
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
        school_cms_id: Optional[int] = None,
        program_cms_id: Optional[int] = None,
        term_code: Optional[str] = None,
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
                    RegistrationRequest.id.label("request_db_id"),
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

            if school_cms_id:
                base_query = base_query.filter(School.cms_id == school_cms_id)

            if program_cms_id:
                base_query = base_query.filter(Program.cms_id == program_cms_id)

            if term_code:
                base_query = base_query.filter(Term.code == term_code)

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
            module_count = self._get_module_count(result.request_db_id)
            rows.append(
                RegistrationRequestRow(
                    request_db_id=result.request_db_id,
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
                    RegistrationRequest.id.label("request_db_id"),
                    Student.std_no,
                    Student.name.label("student_name"),
                    Sponsor.name.label("sponsor_name"),
                    Term.code.label("term_code"),
                    RegistrationRequest.semester_number,
                    RegistrationRequest.semester_status,
                    RegistrationRequest.status,
                    RegistrationRequest.message,
                    RegistrationRequest.created_at,
                    RegistrationRequest.date_registered,
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
                "request_db_id": request.request_db_id,
                "std_no": request.std_no,
                "student_name": request.student_name,
                "sponsor_name": request.sponsor_name,
                "term_code": request.term_code,
                "semester_number": request.semester_number,
                "semester_status": request.semester_status,
                "status": request.status,
                "message": request.message,
                "created_at": request.created_at,
                "date_registered": request.date_registered,
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
                    StudentProgram.id.label("student_program_db_id"),
                    StudentProgram.cms_id.label("student_program_cms_id"),
                    StudentProgram.structure_id.label("structure_db_id"),
                    Structure.cms_id.label("structure_cms_id"),
                )
                .join(Student, RegistrationRequest.std_no == Student.std_no)
                .join(Term, RegistrationRequest.term_id == Term.id)
                .outerjoin(
                    StudentProgram,
                    (StudentProgram.std_no == Student.std_no)
                    & (StudentProgram.status == "Active"),
                )
                .outerjoin(Structure, StudentProgram.structure_id == Structure.id)
                .filter(RegistrationRequest.id == registration_request_id)
                .first()
            )

            if not result:
                return None

            modules = (
                session.query(
                    Module.code.label("module_code"),
                    RequestedModule.module_status,
                    RequestedModule.semester_module_id.label("semester_module_db_id"),
                    SemesterModule.cms_id.label("semester_module_cms_id"),
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
                "student_program_db_id": result.student_program_db_id,
                "student_program_cms_id": result.student_program_cms_id,
                "structure_db_id": result.structure_db_id,
                "structure_cms_id": result.structure_cms_id,
                "modules": modules,
            }

    def get_requested_modules(self, registration_request_id: int):
        with self._session() as session:
            modules = (
                session.query(
                    RequestedModule.id.label("requested_module_db_id"),
                    Module.code.label("module_code"),
                    Module.name.label("module_name"),
                    RequestedModule.module_status,
                    RequestedModule.status,
                    SemesterModule.credits,
                    RequestedModule.semester_module_id.label("semester_module_db_id"),
                    SemesterModule.cms_id.label("semester_module_cms_id"),
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
                    StudentProgram.id.label("student_program_db_id"),
                    StudentProgram.cms_id.label("student_program_cms_id"),
                    StudentProgram.structure_id.label("structure_db_id"),
                    Structure.cms_id.label("structure_cms_id"),
                    StudentProgram.std_no,
                )
                .join(Structure, StudentProgram.structure_id == Structure.id)
                .filter(StudentProgram.std_no == std_no)
                .filter(StudentProgram.status == "Active")
                .first()
            )

            if not program:
                return None

            return {
                "student_program_db_id": program.student_program_db_id,
                "student_program_cms_id": program.student_program_cms_id,
                "structure_db_id": program.structure_db_id,
                "structure_cms_id": program.structure_cms_id,
                "std_no": program.std_no,
            }

    def get_structure_semester_by_number(
        self, structure_db_id: int, semester_number: str
    ):
        with self._session() as session:
            from database import StructureSemester

            semester = (
                session.query(
                    StructureSemester.id.label("structure_semester_db_id"),
                    StructureSemester.cms_id.label("structure_semester_cms_id"),
                )
                .filter(StructureSemester.structure_id == structure_db_id)
                .filter(StructureSemester.semester_number == semester_number)
                .first()
            )

            if not semester:
                return None

            return {
                "structure_semester_db_id": semester.structure_semester_db_id,
                "structure_semester_cms_id": semester.structure_semester_cms_id,
            }

    def get_semester_module_db_id_by_cms_id(
        self, semester_module_cms_id: int
    ) -> Optional[int]:
        with self._session() as session:
            semester_module = (
                session.query(SemesterModule.id)
                .filter(SemesterModule.cms_id == semester_module_cms_id)
                .first()
            )
            return semester_module[0] if semester_module else None

    def upsert_student_semester(
        self, student_program_db_id: int, data: dict
    ) -> tuple[bool, Optional[int]]:
        with self._session() as session:
            from database import StudentSemester

            try:
                semester_id = data.get("cms_id")

                if semester_id:
                    existing = (
                        session.query(StudentSemester)
                        .filter(StudentSemester.cms_id == semester_id)
                        .first()
                    )

                    if not existing:
                        existing_query = session.query(StudentSemester).filter(
                            StudentSemester.student_program_id == student_program_db_id,
                            StudentSemester.cms_id.is_(None),
                        )
                        if data.get("term"):
                            existing_query = existing_query.filter(
                                StudentSemester.term_code == data.get("term")
                            )
                        if data.get("structure_semester_id"):
                            existing_query = existing_query.filter(
                                StudentSemester.structure_semester_id
                                == data.get("structure_semester_id")
                            )
                        existing = existing_query.first()

                    if existing:
                        if semester_id:
                            existing.cms_id = semester_id  # type: ignore
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
                        return True, existing.id
                    else:
                        if (
                            "structure_semester_id" not in data
                            or not data["structure_semester_id"]
                        ):
                            logger.error(
                                f"Cannot create student semester without structure_semester_id - "
                                f"student_program_id={student_program_db_id}, data={data}"
                            )
                            return False, None

                        new_semester = StudentSemester(
                            cms_id=semester_id,
                            student_program_id=student_program_db_id,
                            term_code=data.get("term"),
                            structure_semester_id=data["structure_semester_id"],
                            status=data.get("status", "Active"),
                            caf_date=data.get("caf_date"),
                            sponsor_id=data.get("sponsor_id"),
                            registration_request_id=data.get("registration_request_id"),
                        )
                        session.add(new_semester)
                        session.commit()
                        session.refresh(new_semester)
                        logger.info(f"Created student semester {semester_id}")
                        return True, new_semester.id
                else:
                    logger.error("Cannot create student semester without ID from CMS")
                    return False, None

            except Exception as e:
                session.rollback()
                logger.error(f"Error upserting student semester: {str(e)}")
                return False, None

    def upsert_student_module(self, data: dict) -> bool:
        with self._session() as session:
            from database import StudentModule

            try:
                module_id = data.get("cms_id")
                student_semester_db_id = data.get("student_semester_db_id") or data.get(
                    "student_semester_id"
                )
                semester_module_db_id = data.get("semester_module_db_id")
                if not semester_module_db_id and data.get("semester_module_cms_id"):
                    semester_module_db_id = self.get_semester_module_db_id_by_cms_id(
                        int(data["semester_module_cms_id"])
                    )

                if not module_id:
                    logger.error("Cannot create student module without ID")
                    return False

                if not student_semester_db_id or not semester_module_db_id:
                    logger.error(
                        f"Cannot create student module without resolved database references: {data}"
                    )
                    return False

                existing = (
                    session.query(StudentModule)
                    .filter(StudentModule.cms_id == module_id)
                    .first()
                )

                if not existing:
                    existing = (
                        session.query(StudentModule)
                        .filter(
                            StudentModule.student_semester_id == student_semester_db_id
                        )
                        .filter(
                            StudentModule.semester_module_id == semester_module_db_id
                        )
                        .filter(StudentModule.cms_id.is_(None))
                        .first()
                    )

                if existing:
                    existing.cms_id = module_id  # type: ignore
                    existing.semester_module_id = semester_module_db_id
                    if "status" in data:
                        existing.status = data["status"]
                    if "credits" in data:
                        existing.credits = float(data["credits"])
                    if "marks" in data:
                        existing.marks = data["marks"]
                    if "grade" in data:
                        existing.grade = data["grade"]
                    existing.student_semester_id = student_semester_db_id

                    session.commit()
                    logger.info(f"Updated student module {module_id}")
                    return True
                else:
                    new_module = StudentModule(
                        cms_id=module_id,
                        semester_module_id=semester_module_db_id,
                        status=data.get("status", ""),
                        credits=float(data.get("credits", 0)),
                        marks=data.get("marks", "NM"),
                        grade=data.get("grade", "NM"),
                        student_semester_id=student_semester_db_id,
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

    def update_requested_module_status(
        self, semester_module_id: int, registration_request_id: int, status: str
    ) -> bool:
        with self._session() as session:
            try:
                requested_module = (
                    session.query(RequestedModule)
                    .filter(RequestedModule.semester_module_id == semester_module_id)
                    .filter(
                        RequestedModule.registration_request_id
                        == registration_request_id
                    )
                    .first()
                )

                if not requested_module:
                    logger.warning(
                        f"Requested module not found for semester_module_id={semester_module_id}, "
                        f"registration_request_id={registration_request_id}"
                    )
                    return False

                requested_module.status = status  # type: ignore
                session.commit()
                logger.info(
                    f"Updated requested module status to {status} for semester_module_id={semester_module_id}"
                )
                return True

            except Exception as e:
                session.rollback()
                logger.error(f"Error updating requested module status: {str(e)}")
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
