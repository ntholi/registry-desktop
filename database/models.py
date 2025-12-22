from datetime import datetime
from typing import Literal

import nanoid
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON as PostgreSQLJSON
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

DashboardUser = Literal[
    "finance",
    "registry",
    "library",
    "resource",
    "academic",
    "student_services",
    "admin",
]
UserRole = Literal[
    "user",
    "student",
    "finance",
    "registry",
    "library",
    "resource",
    "academic",
    "student_services",
    "admin",
]
UserPosition = Literal[
    "manager",
    "program_leader",
    "principal_lecturer",
    "year_leader",
    "lecturer",
    "admin",
]

Gender = Literal["Male", "Female", "Unknown"]
MaritalStatus = Literal["Single", "Married", "Divorced", "Windowed", "Other"]

StudentStatus = Literal[
    "Active",
    "Applied",
    "Deceased",
    "Deleted",
    "Graduated",
    "Suspended",
    "Terminated",
    "Withdrawn",
]

EducationType = Literal["Primary", "Secondary", "Tertiary"]

EducationLevel = Literal[
    "JCE",
    "BJCE",
    "BGGSE",
    "BGCSE",
    "LGCSE",
    "IGCSE",
    "O-Levels",
    "A-Levels",
    "Matriculation",
    "Cambridge Oversea School Certificate",
    "Certificate",
    "Diploma",
    "Degree",
    "Masters",
    "Doctorate",
    "Others",
]

NextOfKinRelationship = Literal[
    "Mother",
    "Father",
    "Brother",
    "Sister",
    "Child",
    "Spouse",
    "Guardian",
    "Husband",
    "Wife",
    "Permanent",
    "Self",
    "Other",
]

NextOfKinRelationshipEnum = Enum(
    "Mother",
    "Father",
    "Brother",
    "Sister",
    "Child",
    "Spouse",
    "Guardian",
    "Husband",
    "Wife",
    "Permanent",
    "Self",
    "Other",
    name="next_of_kin_relationship",
    create_constraint=True,
)

StudentProgramStatus = Literal["Active", "Changed", "Completed", "Deleted", "Inactive"]
SemesterStatus = Literal[
    "Active",
    "Outstanding",
    "Deferred",
    "Deleted",
    "DNR",
    "DroppedOut",
    "Withdrawn",
    "Enrolled",
    "Exempted",
    "Inactive",
    "Repeat",
]
SemesterStatusForRegistration = Literal["Active", "Repeat"]

StudentModuleStatus = Literal[
    "Add",
    "Compulsory",
    "Delete",
    "Drop",
    "Exempted",
    "Ineligible",
    "Repeat1",
    "Repeat2",
    "Repeat3",
    "Repeat4",
    "Repeat5",
    "Repeat6",
    "Repeat7",
    "Resit1",
    "Resit2",
    "Resit3",
    "Resit4",
    "Supplementary",
]

Grade = Literal[
    "A+",
    "A",
    "A-",
    "B+",
    "B",
    "B-",
    "C+",
    "C",
    "C-",
    "F",
    "PC",
    "PX",
    "AP",
    "X",
    "DEF",
    "GNS",
    "ANN",
    "FIN",
    "FX",
    "DNC",
    "DNA",
    "PP",
    "DNS",
    "EXP",
    "NM",
]

ProgramLevel = Literal["certificate", "diploma", "degree"]
ModuleStatus = Literal["Active", "Defunct"]
ModuleType = Literal["Major", "Minor", "Core", "Delete", "Elective"]

RegistrationRequestStatus = Literal[
    "pending", "approved", "rejected", "partial", "registered"
]
RequestedModuleStatus = Literal["pending", "registered", "rejected"]
ClearanceRequestStatus = Literal["pending", "approved", "rejected"]
PaymentType = Literal["graduation_gown", "graduation_fee"]

BlockedStudentStatus = Literal["blocked", "unblocked"]

AssessmentNumber = Literal[
    "CW1",
    "CW2",
    "CW3",
    "CW4",
    "CW5",
    "CW6",
    "CW7",
    "CW8",
    "CW9",
    "CW10",
    "CW11",
    "CW12",
    "CW13",
    "CW14",
    "CW15",
]
AssessmentMarksAuditAction = Literal["create", "update", "delete"]
AssessmentsAuditAction = Literal["create", "update", "delete"]
FortinetLevel = Literal["nse1", "nse2", "nse3", "nse4", "nse5", "nse6", "nse7", "nse8"]
FortinetRegistrationStatus = Literal["pending", "approved", "rejected", "completed"]
TaskStatus = Literal["scheduled", "active", "in_progress", "completed", "cancelled"]
TaskPriority = Literal["low", "medium", "high", "urgent"]


def utc_now():
    return datetime.utcnow()


def generate_nanoid():
    return nanoid.generate()


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_nanoid)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[UserRole] = mapped_column(String, nullable=False, default="user")
    position: Mapped[UserPosition | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    emailVerified: Mapped[datetime | None] = mapped_column(
        "email_verified", DateTime, nullable=True
    )
    image: Mapped[str | None] = mapped_column(Text, nullable=True)


class Account(Base):
    __tablename__ = "accounts"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False, primary_key=True)
    provider_account_id: Mapped[str] = mapped_column(
        String, nullable=False, primary_key=True
    )
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    id_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_state: Mapped[str | None] = mapped_column(Text, nullable=True)


class Session(Base):
    __tablename__ = "sessions"

    session_token: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class VerificationToken(Base):
    __tablename__ = "verification_tokens"

    identifier: Mapped[str] = mapped_column(String, nullable=False, primary_key=True)
    token: Mapped[str] = mapped_column(String, nullable=False, primary_key=True)
    expires: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Authenticator(Base):
    __tablename__ = "authenticators"

    credential_id: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    provider_account_id: Mapped[str] = mapped_column(String, nullable=False)
    credential_public_key: Mapped[str] = mapped_column(Text, nullable=False)
    counter: Mapped[int] = mapped_column(Integer, nullable=False)
    credential_device_type: Mapped[str] = mapped_column(String, nullable=False)
    credential_backed_up: Mapped[bool] = mapped_column(Boolean, nullable=False)
    transports: Mapped[str | None] = mapped_column(Text, nullable=True)


class Student(Base):
    __tablename__ = "students"

    std_no: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    national_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[StudentStatus] = mapped_column(
        String, nullable=False, default="Active"
    )
    date_of_birth: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    phone1: Mapped[str | None] = mapped_column(String, nullable=True)
    phone2: Mapped[str | None] = mapped_column(String, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(String, nullable=True)
    marital_status: Mapped[MaritalStatus | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    race: Mapped[str | None] = mapped_column(Text, nullable=True)
    nationality: Mapped[str | None] = mapped_column(Text, nullable=True)
    birth_place: Mapped[str | None] = mapped_column(Text, nullable=True)
    religion: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        Index(
            "idx_students_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index("fk_students_user_id", "user_id"),
    )


class StudentEducation(Base):
    __tablename__ = "student_education"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    school_name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[EducationType | None] = mapped_column(String, nullable=True)
    level: Mapped[EducationLevel | None] = mapped_column(String, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    __table_args__ = (
        Index("fk_student_education_std_no", "std_no"),
        Index("idx_student_education_school_name", "school_name"),
    )


class NextOfKin(Base):
    __tablename__ = "next_of_kins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    relationship: Mapped[NextOfKinRelationship] = mapped_column(
        NextOfKinRelationshipEnum, nullable=False
    )
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (Index("fk_next_of_kins_std_no", "std_no"),)


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[ProgramLevel] = mapped_column(String, nullable=False)
    school_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (Index("fk_programs_school_id", "school_id"),)


class Structure(Base):
    __tablename__ = "structures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    program_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("programs.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (Index("fk_structures_program_id", "program_id"),)


class StudentProgram(Base):
    __tablename__ = "student_programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    intake_date: Mapped[str | None] = mapped_column(String, nullable=True)
    reg_date: Mapped[str | None] = mapped_column(String, nullable=True)
    start_term: Mapped[str | None] = mapped_column(String, nullable=True)
    structure_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("structures.id", ondelete="CASCADE"), nullable=False
    )
    stream: Mapped[str | None] = mapped_column(Text, nullable=True)
    graduation_date: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[StudentProgramStatus] = mapped_column(String, nullable=False)
    assist_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        Index("fk_student_programs_std_no", "std_no"),
        Index("idx_student_programs_status", "status"),
        Index("fk_student_programs_structure_id", "structure_id"),
        Index("idx_student_programs_std_no_status", "std_no", "status"),
    )


class StructureSemester(Base):
    __tablename__ = "structure_semesters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    structure_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("structures.id", ondelete="CASCADE"), nullable=False
    )
    semester_number: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    total_credits: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )


class StudentSemester(Base):
    __tablename__ = "student_semesters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term_code: Mapped[str] = mapped_column(String, nullable=False)
    structure_semester_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("structure_semesters.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[SemesterStatus] = mapped_column(String, nullable=False)
    student_program_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_programs.id", ondelete="CASCADE"), nullable=False
    )
    sponsor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sponsors.id", ondelete="SET NULL"), nullable=True
    )
    caf_date: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        Index("fk_student_semesters_student_program_id", "student_program_id"),
        Index("fk_student_semesters_structure_semester_id", "structure_semester_id"),
        Index("idx_student_semesters_term", "term_code"),
        Index("idx_student_semesters_status", "status"),
        Index("fk_student_semesters_sponsor_id", "sponsor_id"),
    )


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ModuleStatus] = mapped_column(
        String, nullable=False, default="Active"
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[str | None] = mapped_column(Text, nullable=True)


class SemesterModule(Base):
    __tablename__ = "semester_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("modules.id"), nullable=False
    )
    type: Mapped[ModuleType] = mapped_column(String, nullable=False)
    credits: Mapped[float] = mapped_column(Float, nullable=False)
    semester_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("structure_semesters.id", ondelete="SET NULL"),
        nullable=True,
    )
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        Index("fk_semester_modules_module_id", "module_id"),
        Index("fk_semester_modules_semester_id", "semester_id"),
    )


class StudentModule(Base):
    __tablename__ = "student_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    semester_module_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[StudentModuleStatus] = mapped_column(String, nullable=False)
    credits: Mapped[float] = mapped_column(Float, nullable=False)
    marks: Mapped[str] = mapped_column(String, nullable=False)
    grade: Mapped[Grade] = mapped_column(String, nullable=False)
    student_semester_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_semesters.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        Index("fk_student_modules_student_semester_id", "student_semester_id"),
        Index("fk_student_modules_semester_module_id", "semester_module_id"),
        Index("idx_student_modules_status", "status"),
    )


class ModulePrerequisite(Base):
    __tablename__ = "module_prerequisites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    semester_module_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    prerequisite_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (UniqueConstraint("semester_module_id", "prerequisite_id"),)


class Term(Base):
    __tablename__ = "terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    semester: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )


class Sponsor(Base):
    __tablename__ = "sponsors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RegistrationRequest(Base):
    __tablename__ = "registration_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sponsored_student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sponsored_students.id", ondelete="CASCADE"), nullable=False
    )
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    term_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[RegistrationRequestStatus] = mapped_column(
        String, nullable=False, default="pending"
    )
    mail_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    semester_status: Mapped[SemesterStatusForRegistration] = mapped_column(
        String, nullable=False
    )
    semester_number: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    date_approved: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("std_no", "term_id"),
        Index("fk_registration_requests_std_no", "std_no"),
        Index("fk_registration_requests_term_id", "term_id"),
        Index("idx_registration_requests_status", "status"),
        Index("fk_registration_requests_sponsored_student_id", "sponsored_student_id"),
    )


class RequestedModule(Base):
    __tablename__ = "requested_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module_status: Mapped[StudentModuleStatus] = mapped_column(
        String, nullable=False, default="Compulsory"
    )
    registration_request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("registration_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    semester_module_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[RequestedModuleStatus] = mapped_column(
        String, nullable=False, default="pending"
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        Index(
            "fk_requested_modules_registration_request_id", "registration_request_id"
        ),
        Index("fk_requested_modules_semester_module_id", "semester_module_id"),
    )


class Clearance(Base):
    __tablename__ = "clearance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    department: Mapped[DashboardUser] = mapped_column(String, nullable=False)
    status: Mapped[ClearanceRequestStatus] = mapped_column(
        String, nullable=False, default="pending"
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    responded_by: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    response_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        Index("idx_clearance_department", "department"),
        Index("idx_clearance_status", "status"),
    )


class RegistrationClearance(Base):
    __tablename__ = "registration_clearance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    registration_request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("registration_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    clearance_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clearance.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        UniqueConstraint("registration_request_id", "clearance_id"),
        Index(
            "fk_registration_clearance_registration_request_id",
            "registration_request_id",
        ),
        Index("fk_registration_clearance_clearance_id", "clearance_id"),
    )


class GraduationRequest(Base):
    __tablename__ = "graduation_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_program_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("student_programs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    information_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("fk_graduation_requests_student_program_id", "student_program_id"),
    )


class GraduationClearance(Base):
    __tablename__ = "graduation_clearance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    graduation_request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("graduation_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    clearance_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clearance.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        UniqueConstraint("clearance_id"),
        Index("fk_graduation_clearance_graduation_request_id", "graduation_request_id"),
        Index("fk_graduation_clearance_clearance_id", "clearance_id"),
    )


class PaymentReceipt(Base):
    __tablename__ = "payment_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    graduation_request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("graduation_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    payment_type: Mapped[PaymentType] = mapped_column(String, nullable=False)
    receipt_no: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        Index("fk_payment_receipts_graduation_request_id", "graduation_request_id"),
    )


class ClearanceAudit(Base):
    __tablename__ = "clearance_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clearance_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clearance.id", ondelete="CASCADE"), nullable=False
    )
    previous_status: Mapped[RegistrationRequestStatus | None] = mapped_column(
        String, nullable=True
    )
    new_status: Mapped[RegistrationRequestStatus] = mapped_column(
        String, nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    date: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    modules: Mapped[list[str]] = mapped_column(
        PostgreSQLJSON, nullable=False, default=list
    )

    __table_args__ = (
        Index("fk_clearance_audit_clearance_id", "clearance_id"),
        Index("fk_clearance_audit_created_by", "created_by"),
    )


class SponsoredStudent(Base):
    __tablename__ = "sponsored_students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sponsor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sponsors.id", ondelete="CASCADE"), nullable=False
    )
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    borrower_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed: Mapped[bool | None] = mapped_column(
        Boolean, default=False, nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("sponsor_id", "std_no"),
        Index("fk_sponsored_students_sponsor_id", "sponsor_id"),
        Index("fk_sponsored_students_std_no", "std_no"),
    )


class SponsoredTerm(Base):
    __tablename__ = "sponsored_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sponsored_student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sponsored_students.id", ondelete="CASCADE"), nullable=False
    )
    term_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("sponsored_student_id", "term_id"),
        Index("fk_sponsored_terms_sponsored_student_id", "sponsored_student_id"),
        Index("fk_sponsored_terms_term_id", "term_id"),
    )


class AssignedModule(Base):
    __tablename__ = "assigned_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    semester_module_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        Index("fk_assigned_modules_user_id", "user_id"),
        Index("fk_assigned_modules_term_id", "term_id"),
        Index("fk_assigned_modules_semester_module_id", "semester_module_id"),
    )


class UserSchool(Base):
    __tablename__ = "user_schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    school_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "school_id"),
        Index("fk_user_schools_user_id", "user_id"),
        Index("fk_user_schools_school_id", "school_id"),
    )


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    term_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False
    )
    assessment_number: Mapped[AssessmentNumber] = mapped_column(String, nullable=False)
    assessment_type: Mapped[str] = mapped_column(Text, nullable=False)
    total_marks: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        UniqueConstraint("module_id", "assessment_number", "term_id"),
        Index("fk_assessments_module_id", "module_id"),
        Index("fk_assessments_term_id", "term_id"),
    )


class AssessmentMark(Base):
    __tablename__ = "assessment_marks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    marks: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        Index("fk_assessment_marks_assessment_id", "assessment_id"),
        Index("fk_assessment_marks_std_no", "std_no"),
        Index("idx_assessment_marks_assessment_id_std_no", "assessment_id", "std_no"),
    )


class AssessmentMarksAudit(Base):
    __tablename__ = "assessment_marks_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_mark_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("assessment_marks.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[AssessmentMarksAuditAction] = mapped_column(String, nullable=False)
    previous_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    date: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("fk_assessment_marks_audit_assessment_mark_id", "assessment_mark_id"),
        Index("fk_assessment_marks_audit_created_by", "created_by"),
    )


class AssessmentsAudit(Base):
    __tablename__ = "assessments_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[AssessmentsAuditAction] = mapped_column(String, nullable=False)
    previous_assessment_number: Mapped[AssessmentNumber | None] = mapped_column(
        String, nullable=True
    )
    new_assessment_number: Mapped[AssessmentNumber | None] = mapped_column(
        String, nullable=True
    )
    previous_assessment_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_assessment_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_total_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_total_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    date: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("fk_assessments_audit_assessment_id", "assessment_id"),
        Index("fk_assessments_audit_created_by", "created_by"),
    )


class ModuleGrade(Base):
    __tablename__ = "module_grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    grade: Mapped[Grade] = mapped_column(String, nullable=False)
    weighted_total: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (UniqueConstraint("module_id", "std_no"),)


class StatementOfResultsPrint(Base):
    __tablename__ = "statement_of_results_prints"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_nanoid)
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    printed_by: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    student_name: Mapped[str] = mapped_column(Text, nullable=False)
    program_name: Mapped[str] = mapped_column(Text, nullable=False)
    total_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    total_modules: Mapped[int] = mapped_column(Integer, nullable=False)
    cgpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification: Mapped[str | None] = mapped_column(Text, nullable=True)
    academic_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    graduation_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    printed_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    __table_args__ = (
        Index("fk_statement_of_results_prints_std_no", "std_no"),
        Index("fk_statement_of_results_prints_printed_by", "printed_by"),
    )


class TranscriptPrint(Base):
    __tablename__ = "transcript_prints"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_nanoid)
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    printed_by: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    student_name: Mapped[str] = mapped_column(Text, nullable=False)
    program_name: Mapped[str] = mapped_column(Text, nullable=False)
    total_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    cgpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    printed_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    __table_args__ = (
        Index("fk_transcript_prints_std_no", "std_no"),
        Index("fk_transcript_prints_printed_by", "printed_by"),
    )


class BlockedStudent(Base):
    __tablename__ = "blocked_students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[BlockedStudentStatus] = mapped_column(
        String, nullable=False, default="blocked"
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    by_department: Mapped[DashboardUser] = mapped_column(String, nullable=False)
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (Index("fk_blocked_students_std_no", "std_no"),)


class StudentCardPrint(Base):
    __tablename__ = "student_card_prints"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_nanoid)
    receipt_no: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    printed_by: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        Index("fk_student_card_prints_std_no", "std_no"),
        Index("fk_student_card_prints_printed_by", "printed_by"),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_nanoid)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (Index("fk_documents_std_no", "std_no"),)


class FortinetRegistration(Base):
    __tablename__ = "fortinet_registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    std_no: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    school_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[FortinetLevel] = mapped_column(String, nullable=False)
    status: Mapped[FortinetRegistrationStatus] = mapped_column(
        String, nullable=False, default="pending"
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("std_no", "level"),
        Index("fk_fortinet_registrations_std_no", "std_no"),
        Index("fk_fortinet_registrations_school_id", "school_id"),
        Index("idx_fortinet_registrations_status", "status"),
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_nanoid)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(String, nullable=False, default="active")
    priority: Mapped[TaskPriority] = mapped_column(
        String, nullable=False, default="medium"
    )
    department: Mapped[DashboardUser] = mapped_column(String, nullable=False)
    created_by: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("tasks_department_idx", "department"),
        Index("tasks_status_idx", "status"),
        Index("tasks_due_date_idx", "due_date"),
    )


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        UniqueConstraint("task_id", "user_id"),
        Index("fk_task_assignments_user_id", "user_id"),
    )
