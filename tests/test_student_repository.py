import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database import (
    Module,
    Program,
    School,
    SemesterModule,
    Sponsor,
    Structure,
    StructureSemester,
    Student,
    StudentEducation,
    StudentModule,
    StudentProgram,
    StudentSemester,
)
from features.sync.students.repository import StudentRepository


class StudentRepositorySponsorTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Sponsor.__table__.create(self.engine)

        self.repository = StudentRepository()
        self.repository._engine = self.engine
        self.repository.clear_sponsor_cache()

    def tearDown(self):
        self.repository.clear_sponsor_cache()
        self.engine.dispose()

    def _insert_sponsor(self, *, name: str, code: str) -> int:
        with Session(self.engine) as session:
            sponsor = Sponsor(name=name, code=code)
            session.add(sponsor)
            session.commit()
            session.refresh(sponsor)
            return sponsor.id

    def test_lookup_sponsor_matches_existing_name_when_code_differs(self):
        sponsor_id = self._insert_sponsor(name="Self Sponsor", code="SELF")

        resolved_id = self.repository.lookup_sponsor("Self Sponsor")

        self.assertEqual(resolved_id, sponsor_id)

    def test_create_sponsor_reuses_existing_name_instead_of_creating_duplicate(self):
        sponsor_id = self._insert_sponsor(name="Self Sponsor", code="SELF")

        resolved_id = self.repository.create_sponsor("Self Sponsor")

        self.assertEqual(resolved_id, sponsor_id)

        with Session(self.engine) as session:
            sponsors = session.query(Sponsor.id, Sponsor.name, Sponsor.code).all()

        self.assertEqual(len(sponsors), 1)
        self.assertEqual(sponsors[0].id, sponsor_id)
        self.assertEqual(sponsors[0].name, "Self Sponsor")
        self.assertEqual(sponsors[0].code, "SELF")

    def test_create_sponsor_truncates_long_code_values(self):
        sponsor_id = self.repository.create_sponsor("Self Sponsor")

        self.assertIsNotNone(sponsor_id)

        with Session(self.engine) as session:
            sponsors = session.query(Sponsor.id, Sponsor.name, Sponsor.code).all()

        self.assertEqual(len(sponsors), 1)
        self.assertEqual(sponsors[0].id, sponsor_id)
        self.assertEqual(sponsors[0].name, "Self Sponsor")
        self.assertEqual(sponsors[0].code, "Self Spons")


class StudentRepositoryProgramResolutionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for table in [School.__table__, Program.__table__, Structure.__table__]:
            table.create(self.engine)

        self.repository = StudentRepository()
        self.repository._engine = self.engine

    def tearDown(self):
        self.engine.dispose()

    def test_resolve_student_program_structure_id_prefers_program_scoped_match(self):
        with Session(self.engine) as session:
            school = School(code="BUS", name="Business")
            session.add(school)
            session.flush()

            program_bbib = Program(
                code="BBIB",
                name="International Business",
                level="degree",
                school_id=school.id,
            )
            program_bit = Program(
                code="BIT",
                name="Information Technology",
                level="degree",
                school_id=school.id,
            )
            program_at = Program(
                code="AT",
                name="Accounting Technician",
                level="diploma",
                school_id=school.id,
            )
            session.add_all([program_bbib, program_bit, program_at])
            session.flush()

            bit_structure = Structure(
                code="2022-11",
                desc="2022-BIT",
                program_id=program_bit.id,
            )
            bbib_structure = Structure(
                code="2022-IBM",
                desc="2022-11",
                program_id=program_bbib.id,
            )
            at_structure = Structure(
                code="2018-AT",
                desc="1808-AT",
                program_id=program_at.id,
            )
            session.add_all([bit_structure, bbib_structure, at_structure])
            session.commit()
            bbib_structure_id = bbib_structure.id
            at_structure_id = at_structure.id

        resolved_bbib_id = self.repository.resolve_student_program_structure_id(
            "BBIB", "2022-11"
        )
        resolved_at_id = self.repository.resolve_student_program_structure_id(
            "AT", "1808-AT"
        )

        self.assertEqual(resolved_bbib_id, bbib_structure_id)
        self.assertEqual(resolved_at_id, at_structure_id)

    def test_resolve_student_program_structure_id_falls_back_to_start_term_prefix(self):
        with Session(self.engine) as session:
            school = School(code="BUS", name="Business")
            session.add(school)
            session.flush()

            program_int = Program(
                code="INT",
                name="Information Technology",
                level="degree",
                school_id=school.id,
            )
            session.add(program_int)
            session.flush()

            structure_old = Structure(
                code="0802-INT",
                desc="0802-INT",
                program_id=program_int.id,
            )
            structure_target = Structure(
                code="0907-INT.",
                desc="0907-INT",
                program_id=program_int.id,
            )
            structure_new = Structure(
                code="1002-INT",
                desc="1002-INT",
                program_id=program_int.id,
            )
            session.add_all([structure_old, structure_target, structure_new])
            session.commit()
            structure_target_id = structure_target.id

        resolved_id = self.repository.resolve_student_program_structure_id(
            "INT",
            None,
            "2009-07",
            None,
            "2009-09-17",
        )

        self.assertEqual(resolved_id, structure_target_id)


class StudentRepositoryStructureSemesterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for table in [
            School.__table__,
            Program.__table__,
            Structure.__table__,
            StructureSemester.__table__,
        ]:
            table.create(self.engine)

        self.repository = StudentRepository()
        self.repository._engine = self.engine
        self.repository.clear_structure_semester_cache()

    def tearDown(self):
        self.repository.clear_structure_semester_cache()
        self.engine.dispose()

    def test_ensure_structure_semester_creates_placeholder_when_missing(self):
        with Session(self.engine) as session:
            school = School(code="BUS", name="Business")
            session.add(school)
            session.flush()

            program = Program(
                code="BAHR",
                name="Human Resource Management",
                level="degree",
                school_id=school.id,
            )
            session.add(program)
            session.flush()

            structure = Structure(
                code="0802-BAHR",
                desc="0802-BAHR",
                program_id=program.id,
            )
            session.add(structure)
            session.commit()
            structure_id = structure.id

        structure_semester_id = self.repository.ensure_structure_semester(
            structure_id,
            "07",
            "Year 4 Sem 1",
        )

        self.assertIsNotNone(structure_semester_id)
        self.assertEqual(
            self.repository.lookup_structure_semester_id(structure_id, "07"),
            structure_semester_id,
        )

        with Session(self.engine) as session:
            structure_semester = (
                session.query(StructureSemester)
                .filter(StructureSemester.id == structure_semester_id)
                .one()
            )

        self.assertEqual(structure_semester.structure_id, structure_id)
        self.assertEqual(structure_semester.semester_number, "07")
        self.assertEqual(structure_semester.name, "Year 4 Sem 1")
        self.assertEqual(structure_semester.total_credits, 0.0)
        self.assertIsNone(structure_semester.cms_id)


class StudentRepositoryDateCoercionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for table in [Student.__table__, StudentEducation.__table__]:
            table.create(self.engine)

        self.repository = StudentRepository()
        self.repository._engine = self.engine

    def tearDown(self):
        self.engine.dispose()

    def test_update_student_accepts_iso_date_string(self):
        success = self.repository.update_student(
            "901000001",
            {
                "name": "Test Student",
                "date_of_birth": "2001-02-03",
            },
        )

        self.assertTrue(success)

        with Session(self.engine) as session:
            student = session.query(Student).filter(Student.std_no == 901000001).one()

        self.assertEqual(student.date_of_birth, datetime(2001, 2, 3))

    def test_upsert_student_education_accepts_iso_end_date_string(self):
        with Session(self.engine) as session:
            session.add(Student(std_no=901000001, name="Test Student", status="Active"))
            session.commit()

        success, message = self.repository.upsert_student_education(
            {
                "cms_id": 1001,
                "std_no": "901000001",
                "school_name": "Maseru High",
                "type": "Secondary",
                "level": "LGCSE",
                "end_date": "2019-11-01",
            }
        )

        self.assertTrue(success, message)

        with Session(self.engine) as session:
            education = (
                session.query(StudentEducation)
                .filter(StudentEducation.cms_id == 1001)
                .one()
            )

        self.assertEqual(education.end_date, datetime(2019, 11, 1))


class StudentRepositoryStudentModuleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for table in [
            School.__table__,
            Program.__table__,
            Structure.__table__,
            StructureSemester.__table__,
            Module.__table__,
            SemesterModule.__table__,
            Student.__table__,
            StudentProgram.__table__,
            StudentSemester.__table__,
            StudentModule.__table__,
        ]:
            table.create(self.engine)

        self.repository = StudentRepository()
        self.repository._engine = self.engine

    def tearDown(self):
        self.engine.dispose()

    def test_upsert_student_module_creates_matching_type_variant_in_same_semester(self):
        with Session(self.engine) as session:
            school = School(code="BUS", name="Business")
            session.add(school)
            session.flush()

            program = Program(
                code="PR",
                name="Public Relations",
                level="degree",
                school_id=school.id,
            )
            session.add(program)
            session.flush()

            structure = Structure(
                code="1309-PR",
                desc="1309-PR",
                program_id=program.id,
            )
            session.add(structure)
            session.flush()

            structure_semester = StructureSemester(
                structure_id=structure.id,
                semester_number="03",
                name="Semester 3",
                total_credits=20.0,
            )
            session.add(structure_semester)
            session.flush()

            student = Student(std_no=902002456, name="Test Student", status="Active")
            session.add(student)
            session.flush()

            student_program = StudentProgram(
                cms_id=2510,
                std_no=student.std_no,
                structure_id=structure.id,
                status="Active",
            )
            session.add(student_program)
            session.flush()

            student_semester = StudentSemester(
                cms_id=10655,
                term_code="2019-09",
                structure_semester_id=structure_semester.id,
                status="Active",
                student_program_id=student_program.id,
            )
            session.add(student_semester)
            session.flush()

            module = Module(
                code="MAKT101",
                name="Principles of Marketing",
                status="Active",
            )
            session.add(module)
            session.flush()

            session.add(
                SemesterModule(
                    cms_id=914,
                    module_id=module.id,
                    type="Major",
                    credits=3.0,
                    semester_id=structure_semester.id,
                )
            )
            session.commit()

            student_semester_id = student_semester.id
            structure_semester_id = structure_semester.id

        success, message = self.repository.upsert_student_module(
            {
                "cms_id": 55543,
                "student_semester_id": student_semester_id,
                "module_code": "MAKT101",
                "module_name": "Principles of Marketing",
                "type": "Minor",
                "credits": 3.0,
                "status": "Compulsory",
                "marks": "60.0",
                "grade": "B-",
            }
        )

        self.assertTrue(success, message)

        with Session(self.engine) as session:
            student_module = (
                session.query(StudentModule).filter(StudentModule.cms_id == 55543).one()
            )
            linked_semester_module = (
                session.query(SemesterModule)
                .filter(SemesterModule.id == student_module.semester_module_id)
                .one()
            )
            semester_module_types = [
                row.type
                for row in session.query(SemesterModule)
                .join(Module, SemesterModule.module_id == Module.id)
                .filter(Module.code == "MAKT101")
                .filter(SemesterModule.semester_id == structure_semester_id)
                .order_by(SemesterModule.id)
                .all()
            ]

        self.assertEqual(linked_semester_module.type, "Minor")
        self.assertEqual(linked_semester_module.semester_id, structure_semester_id)
        self.assertEqual(semester_module_types, ["Major", "Minor"])


if __name__ == "__main__":
    unittest.main()
