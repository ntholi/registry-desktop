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
    emailVerified = Column(DateTime)
    image = Column(Text)


class Account(Base):
    __tablename__ = "accounts"

    userId = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)
    provider = Column(String, nullable=False, primary_key=True)
    providerAccountId = Column(String, nullable=False, primary_key=True)
    refresh_token = Column(Text)
    access_token = Column(Text)
    expires_at = Column(Integer)
    token_type = Column(Text)
    scope = Column(Text)
    id_token = Column(Text)
    session_state = Column(Text)


class Session(Base):
    __tablename__ = "sessions"

    sessionToken = Column(String, primary_key=True)
    userId = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires = Column(DateTime, nullable=False)


class VerificationToken(Base):
    __tablename__ = "verification_tokens"

    identifier = Column(String, nullable=False, primary_key=True)
    token = Column(String, nullable=False, primary_key=True)
    expires = Column(DateTime, nullable=False)


class Authenticator(Base):
    __tablename__ = "authenticators"

    credentialID = Column(String, nullable=False, unique=True)
    userId = Column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    providerAccountId = Column(String, nullable=False)
    credentialPublicKey = Column(Text, nullable=False)
    counter = Column(Integer, nullable=False)
    credentialDeviceType = Column(String, nullable=False)
    credentialBackedUp = Column(Boolean, nullable=False)
    transports = Column(Text)


class Signup(Base):
    __tablename__ = "signups"

    userId = Column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    name = Column(Text, nullable=False)
    stdNo = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    message = Column(Text, default="Pending approval")
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime)


class Student(Base):
    __tablename__ = "students"

    stdNo = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    nationalId = Column(String, nullable=False)
    sem = Column(Integer, nullable=False)
    dateOfBirth = Column(DateTime)
    phone1 = Column(String)
    phone2 = Column(String)
    gender = Column(String)
    maritalStatus = Column(String)
    religion = Column(Text)
    userId = Column(String, ForeignKey("users.id", ondelete="SET NULL"))
    createdAt = Column(DateTime, default=datetime.utcnow)


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    isActive = Column(Boolean, nullable=False, default=True)
    createdAt = Column(DateTime, default=datetime.utcnow)


class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    level = Column(String, nullable=False)
    schoolId = Column(
        Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    createdAt = Column(DateTime, default=datetime.utcnow)


class Structure(Base):
    __tablename__ = "structures"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    desc = Column(Text)
    programId = Column(
        Integer, ForeignKey("programs.id", ondelete="CASCADE"), nullable=False
    )
    createdAt = Column(DateTime, default=datetime.utcnow)


class StudentProgram(Base):
    __tablename__ = "student_programs"

    id = Column(Integer, primary_key=True)
    stdNo = Column(
        Integer, ForeignKey("students.stdNo", ondelete="CASCADE"), nullable=False
    )
    intakeDate = Column(String)
    regDate = Column(String)
    startTerm = Column(String)
    structureId = Column(
        Integer, ForeignKey("structures.id", ondelete="CASCADE"), nullable=False
    )
    stream = Column(Text)
    graduationDate = Column(String)
    status = Column(String, nullable=False)
    assistProvider = Column(Text)
    createdAt = Column(DateTime, default=datetime.utcnow)


class StructureSemester(Base):
    __tablename__ = "structure_semesters"

    id = Column(Integer, primary_key=True)
    structureId = Column(
        Integer, ForeignKey("structures.id", ondelete="CASCADE"), nullable=False
    )
    semesterNumber = Column(Integer, nullable=False)
    name = Column(Text, nullable=False)
    totalCredits = Column(Float, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)


class StudentSemester(Base):
    __tablename__ = "student_semesters"

    id = Column(Integer, primary_key=True)
    term = Column(String, nullable=False)
    semesterNumber = Column(Integer)
    status = Column(String, nullable=False)
    studentProgramId = Column(
        Integer, ForeignKey("student_programs.id", ondelete="CASCADE"), nullable=False
    )
    cafDate = Column(String)
    createdAt = Column(DateTime, default=datetime.utcnow)


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
    moduleId = Column(Integer, ForeignKey("modules.id"))
    type = Column(String, nullable=False)
    credits = Column(Float, nullable=False)
    semesterId = Column(
        Integer, ForeignKey("structure_semesters.id", ondelete="SET NULL")
    )
    hidden = Column(Boolean, nullable=False, default=False)
    createdAt = Column(DateTime, default=datetime.utcnow)


class StudentModule(Base):
    __tablename__ = "student_modules"

    id = Column(Integer, primary_key=True)
    semesterModuleId = Column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(String, nullable=False)
    marks = Column(String, nullable=False)
    grade = Column(String, nullable=False)
    studentSemesterId = Column(
        Integer, ForeignKey("student_semesters.id", ondelete="CASCADE"), nullable=False
    )
    createdAt = Column(DateTime, default=datetime.utcnow)


class ModulePrerequisite(Base):
    __tablename__ = "module_prerequisites"

    id = Column(Integer, primary_key=True)
    semesterModuleId = Column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    prerequisiteId = Column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    createdAt = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("semesterModuleId", "prerequisiteId"),)


class Term(Base):
    __tablename__ = "terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    isActive = Column(Boolean, nullable=False, default=False)
    semester = Column(Integer, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)


class Sponsor(Base):
    __tablename__ = "sponsors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime)


class RegistrationRequest(Base):
    __tablename__ = "registration_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sponsorId = Column(
        Integer, ForeignKey("sponsors.id", ondelete="CASCADE"), nullable=False
    )
    stdNo = Column(
        Integer, ForeignKey("students.stdNo", ondelete="CASCADE"), nullable=False
    )
    termId = Column(Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False, default="pending")
    mailSent = Column(Boolean, nullable=False, default=False)
    count = Column(Integer, nullable=False, default=1)
    semesterStatus = Column(String, nullable=False)
    semesterNumber = Column(Integer, nullable=False)
    message = Column(Text)
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime)
    dateApproved = Column(DateTime)

    __table_args__ = (UniqueConstraint("stdNo", "termId"),)


class RequestedModule(Base):
    __tablename__ = "requested_modules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    moduleStatus = Column(String, nullable=False, default="Compulsory")
    registrationRequestId = Column(
        Integer,
        ForeignKey("registration_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    semesterModuleId = Column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(String, nullable=False, default="pending")
    createdAt = Column(DateTime, default=datetime.utcnow)


class Clearance(Base):
    __tablename__ = "clearance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    department = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    message = Column(Text)
    emailSent = Column(Boolean, nullable=False, default=False)
    respondedBy = Column(String, ForeignKey("users.id", ondelete="CASCADE"))
    responseDate = Column(DateTime)
    createdAt = Column(DateTime, default=datetime.utcnow)


class RegistrationClearance(Base):
    __tablename__ = "registration_clearance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    registrationRequestId = Column(
        Integer,
        ForeignKey("registration_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    clearanceId = Column(
        Integer, ForeignKey("clearance.id", ondelete="CASCADE"), nullable=False
    )
    createdAt = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("registrationRequestId", "clearanceId"),)


class GraduationRequest(Base):
    __tablename__ = "graduation_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    studentProgramId = Column(
        Integer,
        ForeignKey("student_programs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    informationConfirmed = Column(Boolean, nullable=False, default=False)
    message = Column(Text)
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime)


class GraduationClearance(Base):
    __tablename__ = "graduation_clearance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    graduationRequestId = Column(
        Integer,
        ForeignKey("graduation_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    clearanceId = Column(
        Integer, ForeignKey("clearance.id", ondelete="CASCADE"), nullable=False
    )
    createdAt = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("clearanceId"),)


class GraduationList(Base):
    __tablename__ = "graduation_lists"

    id = Column(String, primary_key=True)
    name = Column(Text, nullable=False, default="Graduation List")
    spreadsheetId = Column(Text)
    spreadsheetUrl = Column(Text)
    status = Column(String, nullable=False, default="created")
    createdBy = Column(String, ForeignKey("users.id", ondelete="SET NULL"))
    populatedAt = Column(DateTime)
    createdAt = Column(DateTime, default=datetime.utcnow)


class PaymentReceipt(Base):
    __tablename__ = "payment_receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    graduationRequestId = Column(
        Integer,
        ForeignKey("graduation_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    paymentType = Column(String, nullable=False)
    receiptNo = Column(String, nullable=False, unique=True)
    createdAt = Column(DateTime, default=datetime.utcnow)


class ClearanceAudit(Base):
    __tablename__ = "clearance_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clearanceId = Column(
        Integer, ForeignKey("clearance.id", ondelete="CASCADE"), nullable=False
    )
    previousStatus = Column(String)
    newStatus = Column(String, nullable=False)
    createdBy = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    date = Column(DateTime, default=datetime.utcnow, nullable=False)
    message = Column(Text)
    modules = Column(Text)


class SponsoredStudent(Base):
    __tablename__ = "sponsored_students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sponsorId = Column(
        Integer, ForeignKey("sponsors.id", ondelete="CASCADE"), nullable=False
    )
    stdNo = Column(
        Integer, ForeignKey("students.stdNo", ondelete="CASCADE"), nullable=False
    )
    borrowerNo = Column(Text)
    bankName = Column(Text)
    accountNumber = Column(Text)
    confirmed = Column(Boolean, default=False)
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime)

    __table_args__ = (UniqueConstraint("sponsorId", "stdNo"),)


class SponsoredTerm(Base):
    __tablename__ = "sponsored_terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sponsoredStudentId = Column(
        Integer, ForeignKey("sponsored_students.id", ondelete="CASCADE"), nullable=False
    )
    termId = Column(Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime)

    __table_args__ = (UniqueConstraint("sponsoredStudentId", "termId"),)


class AssignedModule(Base):
    __tablename__ = "assigned_modules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    termId = Column(Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    userId = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    semesterModuleId = Column(
        Integer, ForeignKey("semester_modules.id", ondelete="CASCADE"), nullable=False
    )
    createdAt = Column(DateTime, default=datetime.utcnow)


class UserSchool(Base):
    __tablename__ = "user_schools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    userId = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    schoolId = Column(
        Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    createdAt = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("userId", "schoolId"),)


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    moduleId = Column(
        Integer, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    termId = Column(Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    assessmentNumber = Column(String, nullable=False)
    assessmentType = Column(Text, nullable=False)
    totalMarks = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("moduleId", "assessmentNumber", "termId"),)


class AssessmentMark(Base):
    __tablename__ = "assessment_marks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessmentId = Column(
        Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    stdNo = Column(
        Integer, ForeignKey("students.stdNo", ondelete="CASCADE"), nullable=False
    )
    marks = Column(Float, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)


class AssessmentMarksAudit(Base):
    __tablename__ = "assessment_marks_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessmentMarkId = Column(
        Integer, ForeignKey("assessment_marks.id", ondelete="SET NULL")
    )
    action = Column(String, nullable=False)
    previousMarks = Column(Float)
    newMarks = Column(Float)
    createdBy = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    date = Column(DateTime, default=datetime.utcnow, nullable=False)


class AssessmentsAudit(Base):
    __tablename__ = "assessments_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessmentId = Column(Integer, ForeignKey("assessments.id", ondelete="SET NULL"))
    action = Column(String, nullable=False)
    previousAssessmentNumber = Column(String)
    newAssessmentNumber = Column(String)
    previousAssessmentType = Column(Text)
    newAssessmentType = Column(Text)
    previousTotalMarks = Column(Float)
    newTotalMarks = Column(Float)
    previousWeight = Column(Float)
    newWeight = Column(Float)
    createdBy = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    date = Column(DateTime, default=datetime.utcnow, nullable=False)


class ModuleGrade(Base):
    __tablename__ = "module_grades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    moduleId = Column(
        Integer, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    stdNo = Column(
        Integer, ForeignKey("students.stdNo", ondelete="CASCADE"), nullable=False
    )
    grade = Column(String, nullable=False)
    weightedTotal = Column(Float, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("moduleId", "stdNo"),)


class StatementOfResultsPrint(Base):
    __tablename__ = "statement_of_results_prints"

    id = Column(String, primary_key=True)
    stdNo = Column(
        Integer, ForeignKey("students.stdNo", ondelete="CASCADE"), nullable=False
    )
    printedBy = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    studentName = Column(Text, nullable=False)
    programName = Column(Text, nullable=False)
    totalCredits = Column(Integer, nullable=False)
    totalModules = Column(Integer, nullable=False)
    cgpa = Column(Float)
    classification = Column(Text)
    academicStatus = Column(Text)
    graduationDate = Column(Text)
    printedAt = Column(DateTime, default=datetime.utcnow, nullable=False)


class TranscriptPrint(Base):
    __tablename__ = "transcript_prints"

    id = Column(String, primary_key=True)
    stdNo = Column(
        Integer, ForeignKey("students.stdNo", ondelete="CASCADE"), nullable=False
    )
    printedBy = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    studentName = Column(Text, nullable=False)
    programName = Column(Text, nullable=False)
    totalCredits = Column(Integer, nullable=False)
    cgpa = Column(Float)
    printedAt = Column(DateTime, default=datetime.utcnow, nullable=False)


class BlockedStudent(Base):
    __tablename__ = "blocked_students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String, nullable=False, default="blocked")
    reason = Column(Text, nullable=False)
    byDepartment = Column(String, nullable=False)
    stdNo = Column(
        Integer, ForeignKey("students.stdNo", ondelete="CASCADE"), nullable=False
    )
    createdAt = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("blocked_students_std_no_idx", "stdNo"),)


class StudentCardPrint(Base):
    __tablename__ = "student_card_prints"

    id = Column(String, primary_key=True)
    receiptNo = Column(String, nullable=False, unique=True)
    stdNo = Column(
        Integer, ForeignKey("students.stdNo", ondelete="CASCADE"), nullable=False
    )
    printedBy = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    createdAt = Column(DateTime, default=datetime.utcnow)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    fileName = Column(Text, nullable=False)
    type = Column(Text)
    stdNo = Column(
        Integer, ForeignKey("students.stdNo", ondelete="CASCADE"), nullable=False
    )
    createdAt = Column(DateTime, default=datetime.utcnow)
