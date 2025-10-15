from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(Text)
    role = Column(String, nullable=False, default="user")
    position = Column(String)
    email = Column(String, unique=True)
    email_verified = Column(DateTime)
    image = Column(Text)


class Account(Base):
    __tablename__ = "accounts"

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)
    provider = Column(String, nullable=False, primary_key=True)
    provider_account_id = Column(String, nullable=False, primary_key=True)
    refresh_token = Column(Text)
    access_token = Column(Text)
    expires_at = Column(Integer)
    token_type = Column(Text)
    scope = Column(Text)
    id_token = Column(Text)
    session_state = Column(Text)


class Session(Base):
    __tablename__ = "sessions"

    session_token = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires = Column(DateTime, nullable=False)


class VerificationToken(Base):
    __tablename__ = "verification_tokens"

    identifier = Column(String, nullable=False, primary_key=True)
    token = Column(String, nullable=False, primary_key=True)
    expires = Column(DateTime, nullable=False)


class Authenticator(Base):
    __tablename__ = "authenticators"

    credential_id = Column(String, nullable=False, unique=True)
    user_id = Column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    provider_account_id = Column(String, nullable=False)
    credential_public_key = Column(Text, nullable=False)
    counter = Column(Integer, nullable=False)
    credential_device_type = Column(String, nullable=False)
    credential_backed_up = Column(Boolean, nullable=False)
    transports = Column(Text)


class Signup(Base):
    __tablename__ = "signups"

    user_id = Column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    name = Column(Text, nullable=False)
    std_no = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    message = Column(Text, default="Pending approval")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)


class Student(Base):
    __tablename__ = "students"

    std_no = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    national_id = Column(String, nullable=False)
    sem = Column(Integer, nullable=False)
    date_of_birth = Column(DateTime)
    phone1 = Column(String)
    phone2 = Column(String)
    gender = Column(String)
    marital_status = Column(String)
    religion = Column(Text)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow)


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    level = Column(String, nullable=False)
    school_id = Column(
        Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)


class Structure(Base):
    __tablename__ = "structures"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    desc = Column(Text)
    program_id = Column(
        Integer, ForeignKey("programs.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)


class StudentProgram(Base):
    __tablename__ = "student_programs"

    id = Column(Integer, primary_key=True)
    std_no = Column(
        Integer, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    intake_date = Column(String)
    reg_date = Column(String)
    start_term = Column(String)
    structure_id = Column(
        Integer, ForeignKey("structures.id", ondelete="CASCADE"), nullable=False
    )
    stream = Column(Text)
    graduation_date = Column(String)
    status = Column(String, nullable=False)
    assist_provider = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class StructureSemester(Base):
    __tablename__ = "structure_semesters"

    id = Column(Integer, primary_key=True)
    structure_id = Column(
        Integer, ForeignKey("structures.id", ondelete="CASCADE"), nullable=False
    )
    semester_number = Column(Integer, nullable=False)
    name = Column(Text, nullable=False)
    total_credits = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class StudentSemester(Base):
    __tablename__ = "student_semesters"

    id = Column(Integer, primary_key=True)
    term = Column(String, nullable=False)
    semester_number = Column(Integer)
    status = Column(String, nullable=False)
    student_program_id = Column(
        Integer, ForeignKey("student_programs.id", ondelete="CASCADE"), nullable=False
    )
    caf_date = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Module(Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False)
    name = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="Active")
    timestamp = Column(Text)


class SemesterModule(Base):
    __tablename__ = "semester_modules"

    id = Column(Integer, primary_key=True)
    module_id = Column(Integer, ForeignKey("modules.id"))
    type = Column(String, nullable=False)
    credits = Column(Float, nullable=False)
    semester_id = Column(
        Integer, ForeignKey("structure_semesters.id", ondelete="SET NULL")
    )
    hidden = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class StudentModule(Base):
    __tablename__ = "student_modules"

    id = Column(Integer, primary_key=True)
    semester_module_id = Column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(String, nullable=False)
    marks = Column(String, nullable=False)
    grade = Column(String, nullable=False)
    student_semester_id = Column(
        Integer, ForeignKey("student_semesters.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)


class ModulePrerequisite(Base):
    __tablename__ = "module_prerequisites"

    id = Column(Integer, primary_key=True)
    semester_module_id = Column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    prerequisite_id = Column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("semester_module_id", "prerequisite_id"),)


class Term(Base):
    __tablename__ = "terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, default=False)
    semester = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Sponsor(Base):
    __tablename__ = "sponsors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)


class RegistrationRequest(Base):
    __tablename__ = "registration_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sponsor_id = Column(
        Integer, ForeignKey("sponsors.id", ondelete="CASCADE"), nullable=False
    )
    std_no = Column(
        Integer, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    term_id = Column(
        Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(String, nullable=False, default="pending")
    mail_sent = Column(Boolean, nullable=False, default=False)
    count = Column(Integer, nullable=False, default=1)
    semester_status = Column(String, nullable=False)
    semester_number = Column(Integer, nullable=False)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)
    date_approved = Column(DateTime)

    __table_args__ = (UniqueConstraint("std_no", "term_id"),)


class RequestedModule(Base):
    __tablename__ = "requested_modules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    module_status = Column(String, nullable=False, default="Compulsory")
    registration_request_id = Column(
        Integer,
        ForeignKey("registration_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    semester_module_id = Column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


class Clearance(Base):
    __tablename__ = "clearance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    department = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    message = Column(Text)
    email_sent = Column(Boolean, nullable=False, default=False)
    responded_by = Column(String, ForeignKey("users.id", ondelete="CASCADE"))
    response_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class RegistrationClearance(Base):
    __tablename__ = "registration_clearance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    registration_request_id = Column(
        Integer,
        ForeignKey("registration_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    clearance_id = Column(
        Integer, ForeignKey("clearance.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("registration_request_id", "clearance_id"),)


class GraduationRequest(Base):
    __tablename__ = "graduation_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_program_id = Column(
        Integer,
        ForeignKey("student_programs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    information_confirmed = Column(Boolean, nullable=False, default=False)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)


class GraduationClearance(Base):
    __tablename__ = "graduation_clearance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    graduation_request_id = Column(
        Integer,
        ForeignKey("graduation_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    clearance_id = Column(
        Integer, ForeignKey("clearance.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("clearance_id"),)


class GraduationList(Base):
    __tablename__ = "graduation_lists"

    id = Column(String, primary_key=True)
    name = Column(Text, nullable=False, default="Graduation List")
    spreadsheet_id = Column(Text)
    spreadsheet_url = Column(Text)
    status = Column(String, nullable=False, default="created")
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"))
    populated_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class PaymentReceipt(Base):
    __tablename__ = "payment_receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    graduation_request_id = Column(
        Integer,
        ForeignKey("graduation_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    payment_type = Column(String, nullable=False)
    receipt_no = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClearanceAudit(Base):
    __tablename__ = "clearance_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clearance_id = Column(
        Integer, ForeignKey("clearance.id", ondelete="CASCADE"), nullable=False
    )
    previous_status = Column(String)
    new_status = Column(String, nullable=False)
    created_by = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    date = Column(DateTime, default=datetime.utcnow, nullable=False)
    message = Column(Text)
    modules = Column(Text)


class SponsoredStudent(Base):
    __tablename__ = "sponsored_students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sponsor_id = Column(
        Integer, ForeignKey("sponsors.id", ondelete="CASCADE"), nullable=False
    )
    std_no = Column(
        Integer, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    borrower_no = Column(Text)
    bank_name = Column(Text)
    account_number = Column(Text)
    confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)

    __table_args__ = (UniqueConstraint("sponsor_id", "std_no"),)


class SponsoredTerm(Base):
    __tablename__ = "sponsored_terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sponsored_student_id = Column(
        Integer, ForeignKey("sponsored_students.id", ondelete="CASCADE"), nullable=False
    )
    term_id = Column(
        Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)

    __table_args__ = (UniqueConstraint("sponsored_student_id", "term_id"),)


class AssignedModule(Base):
    __tablename__ = "assigned_modules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    term_id = Column(
        Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False
    )
    active = Column(Boolean, nullable=False, default=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    semester_module_id = Column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)


class UserSchool(Base):
    __tablename__ = "user_schools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    school_id = Column(
        Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "school_id"),)


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    module_id = Column(
        Integer, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    term_id = Column(
        Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False
    )
    assessment_number = Column(String, nullable=False)
    assessment_type = Column(Text, nullable=False)
    total_marks = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("module_id", "assessment_number", "term_id"),)


class AssessmentMark(Base):
    __tablename__ = "assessment_marks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(
        Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    std_no = Column(
        Integer, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    marks = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AssessmentMarksAudit(Base):
    __tablename__ = "assessment_marks_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_mark_id = Column(
        Integer, ForeignKey("assessment_marks.id", ondelete="SET NULL")
    )
    action = Column(String, nullable=False)
    previous_marks = Column(Float)
    new_marks = Column(Float)
    created_by = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    date = Column(DateTime, default=datetime.utcnow, nullable=False)


class AssessmentsAudit(Base):
    __tablename__ = "assessments_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="SET NULL"))
    action = Column(String, nullable=False)
    previous_assessment_number = Column(String)
    new_assessment_number = Column(String)
    previous_assessment_type = Column(Text)
    new_assessment_type = Column(Text)
    previous_total_marks = Column(Float)
    new_total_marks = Column(Float)
    previous_weight = Column(Float)
    new_weight = Column(Float)
    created_by = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    date = Column(DateTime, default=datetime.utcnow, nullable=False)


class ModuleGrade(Base):
    __tablename__ = "module_grades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    module_id = Column(
        Integer, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    std_no = Column(
        Integer, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    grade = Column(String, nullable=False)
    weighted_total = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("module_id", "std_no"),)


class StatementOfResultsPrint(Base):
    __tablename__ = "statement_of_results_prints"

    id = Column(String, primary_key=True)
    std_no = Column(
        Integer, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    printed_by = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    student_name = Column(Text, nullable=False)
    program_name = Column(Text, nullable=False)
    total_credits = Column(Integer, nullable=False)
    total_modules = Column(Integer, nullable=False)
    cgpa = Column(Float)
    classification = Column(Text)
    academic_status = Column(Text)
    graduation_date = Column(Text)
    printed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TranscriptPrint(Base):
    __tablename__ = "transcript_prints"

    id = Column(String, primary_key=True)
    std_no = Column(
        Integer, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    printed_by = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    student_name = Column(Text, nullable=False)
    program_name = Column(Text, nullable=False)
    total_credits = Column(Integer, nullable=False)
    cgpa = Column(Float)
    printed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BlockedStudent(Base):
    __tablename__ = "blocked_students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String, nullable=False, default="blocked")
    reason = Column(Text, nullable=False)
    by_department = Column(String, nullable=False)
    std_no = Column(
        Integer, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("blocked_students_std_no_idx", "std_no"),)


class StudentCardPrint(Base):
    __tablename__ = "student_card_prints"

    id = Column(String, primary_key=True)
    receiptNo = Column(String, nullable=False, unique=True)
    receipt_no = Column(String, nullable=False, unique=True)
    std_no = Column(
        Integer, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    printed_by = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    file_name = Column(Text, nullable=False)
    type = Column(Text)
    std_no = Column(
        Integer, ForeignKey("students.std_no", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)
