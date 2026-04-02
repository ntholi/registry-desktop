from datetime import datetime
from typing import Literal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
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

ProgramLevel = Literal["certificate", "diploma", "degree", "short_course"]
ModuleStatus = Literal["Active", "Defunct"]
ModuleType = Literal["Major", "Minor", "Core", "Delete", "Elective"]

RegistrationRequestStatus = Literal[
    "pending", "approved", "rejected", "partial", "registered"
]
RequestedModuleStatus = Literal["pending", "registered", "rejected"]
ClearanceRequestStatus = Literal["pending", "approved", "rejected"]

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


def utc_now():
    return datetime.utcnow()


Base = declarative_base()


class Student(Base):
    __tablename__ = "students"

    std_no: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    national_id: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    zoho_contact_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "idx_students_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
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
    cms_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
        PgEnum(
            "Parent",
            "Brother",
            "Sister",
            "Spouse",
            "Child",
            "Relative",
            "Friend",
            "Guardian",
            "Other",
            "Mother",
            "Father",
            "Husband",
            "Wife",
            "Permanent",
            "Self",
            name="next_of_kin_relationship",
            create_type=False,
        ),
        nullable=False,
    )
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    occupation: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    cms_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
    cms_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    short_name: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    cms_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
    cms_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
    cms_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
    cms_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


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
    sponsor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caf_date: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    cms_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
    cms_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


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
    cms_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
    cms_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("fk_student_modules_student_semester_id", "student_semester_id"),
        Index("fk_student_modules_semester_module_id", "semester_module_id"),
        Index("idx_student_modules_status", "status"),
    )


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
    sponsored_student_id: Mapped[int] = mapped_column(Integer, nullable=False)
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
    semester_number: Mapped[str] = mapped_column(String(2), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    date_registered: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    student_semester_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("student_semesters.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
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
    responded_by: Mapped[str | None] = mapped_column(String, nullable=True)
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
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("sponsor_id", "std_no"),
        Index("fk_sponsored_students_sponsor_id", "sponsor_id"),
        Index("fk_sponsored_students_std_no", "std_no"),
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
    student_module_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_modules.id", ondelete="CASCADE"), nullable=False
    )
    marks: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )

    __table_args__ = (
        Index("fk_assessment_marks_assessment_id", "assessment_id"),
        Index("fk_assessment_marks_student_module_id", "student_module_id"),
        Index(
            "idx_assessment_marks_assessment_id_student_module_id",
            "assessment_id",
            "student_module_id",
        ),
    )
