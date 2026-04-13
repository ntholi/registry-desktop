import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import Base, NextOfKin, Student, StudentEducation
from tools.upload_data import (
    STUDENT_FILLABLE_FIELDS,
    AnalysisResult,
    Conflict,
    MergeStats,
    analyze_differences,
    merge_next_of_kins,
    merge_student_education,
    merge_students,
    run_merge,
)


def _create_test_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _add_student(
    session: Session,
    std_no: int,
    name: str = "Test Student",
    status: str = "Active",
    **kwargs: object,
) -> Student:
    s = Student(std_no=std_no, name=name, status=status, **kwargs)
    session.add(s)
    session.flush()
    return s


class TestMergeStudentsAdd(unittest.TestCase):
    def setUp(self) -> None:
        self.source_engine = _create_test_engine()
        self.target_engine = _create_test_engine()

    def tearDown(self) -> None:
        self.source_engine.dispose()
        self.target_engine.dispose()

    def test_add_new_student(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", country="Lesotho", gender="Female")
            src.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(result.name, "Alice")
            self.assertEqual(result.country, "Lesotho")
            self.assertEqual(result.gender, "Female")
            self.assertEqual(result.status, "Active")

        self.assertEqual(stats.students_added, 1)
        self.assertEqual(stats.students_updated, 0)
        self.assertEqual(stats.students_skipped, 0)

    def test_add_multiple_new_students(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            _add_student(src, 100002, "Bob")
            _add_student(src, 100003, "Charlie")
            src.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            count = tgt.query(Student).count()
            self.assertEqual(count, 3)

        self.assertEqual(stats.students_added, 3)

    def test_add_student_preserves_all_fields(self) -> None:
        dob = datetime(2000, 1, 15)
        with Session(self.source_engine) as src:
            _add_student(
                src,
                100001,
                "Alice Johnson",
                national_id="ID123",
                date_of_birth=dob,
                phone1="+266 5000",
                phone2="+266 6000",
                gender="Female",
                marital_status="Single",
                country="Lesotho",
                race="African",
                nationality="Mosotho",
                birth_place="Maseru",
                religion="Christian",
            )
            src.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(result.name, "Alice Johnson")
            self.assertEqual(result.national_id, "ID123")
            self.assertEqual(result.date_of_birth, dob)
            self.assertEqual(result.phone1, "+266 5000")
            self.assertEqual(result.phone2, "+266 6000")
            self.assertEqual(result.gender, "Female")
            self.assertEqual(result.marital_status, "Single")
            self.assertEqual(result.country, "Lesotho")
            self.assertEqual(result.race, "African")
            self.assertEqual(result.nationality, "Mosotho")
            self.assertEqual(result.birth_place, "Maseru")
            self.assertEqual(result.religion, "Christian")


class TestMergeStudentsUpdate(unittest.TestCase):
    def setUp(self) -> None:
        self.source_engine = _create_test_engine()
        self.target_engine = _create_test_engine()

    def tearDown(self) -> None:
        self.source_engine.dispose()
        self.target_engine.dispose()

    def test_fill_null_country(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", country="Lesotho")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(result.country, "Lesotho")

        self.assertEqual(stats.students_updated, 1)
        self.assertEqual(stats.students_fields_filled.get("country"), 1)

    def test_fill_multiple_null_fields(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(
                src,
                100001,
                "Alice",
                country="Lesotho",
                race="African",
                nationality="Mosotho",
                birth_place="Maseru",
            )
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(result.country, "Lesotho")
            self.assertEqual(result.race, "African")
            self.assertEqual(result.nationality, "Mosotho")
            self.assertEqual(result.birth_place, "Maseru")

        self.assertEqual(stats.students_updated, 1)
        self.assertEqual(stats.students_fields_filled.get("country"), 1)
        self.assertEqual(stats.students_fields_filled.get("race"), 1)
        self.assertEqual(stats.students_fields_filled.get("nationality"), 1)
        self.assertEqual(stats.students_fields_filled.get("birth_place"), 1)

    def test_no_overwrite_existing_country(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", country="South Africa")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice", country="Lesotho")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(result.country, "Lesotho")

        self.assertEqual(stats.students_skipped, 1)

    def test_no_overwrite_any_field(self) -> None:
        dob_src = datetime(2000, 1, 1)
        dob_tgt = datetime(1999, 12, 31)
        with Session(self.source_engine) as src:
            _add_student(
                src,
                100001,
                "Source Name",
                status="Applied",
                national_id="SRC_ID",
                date_of_birth=dob_src,
                phone1="SRC_P1",
                phone2="SRC_P2",
                gender="Male",
                marital_status="Married",
                country="SRC Country",
                race="SRC Race",
                nationality="SRC Nat",
                birth_place="SRC Place",
                religion="SRC Religion",
            )
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(
                tgt,
                100001,
                "Target Name",
                status="Active",
                national_id="TGT_ID",
                date_of_birth=dob_tgt,
                phone1="TGT_P1",
                phone2="TGT_P2",
                gender="Female",
                marital_status="Single",
                country="TGT Country",
                race="TGT Race",
                nationality="TGT Nat",
                birth_place="TGT Place",
                religion="TGT Religion",
            )
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(result.name, "Target Name")
            self.assertEqual(result.status, "Active")
            self.assertEqual(result.national_id, "TGT_ID")
            self.assertEqual(result.date_of_birth, dob_tgt)
            self.assertEqual(result.phone1, "TGT_P1")
            self.assertEqual(result.phone2, "TGT_P2")
            self.assertEqual(result.gender, "Female")
            self.assertEqual(result.marital_status, "Single")
            self.assertEqual(result.country, "TGT Country")
            self.assertEqual(result.race, "TGT Race")
            self.assertEqual(result.nationality, "TGT Nat")
            self.assertEqual(result.birth_place, "TGT Place")
            self.assertEqual(result.religion, "TGT Religion")

        self.assertEqual(stats.students_skipped, 1)

    def test_fill_partial_null_fields(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(
                src, 100001, "Alice", country="Lesotho", race="African", gender="Female"
            )
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice", gender="Female")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(result.country, "Lesotho")
            self.assertEqual(result.race, "African")
            self.assertEqual(result.gender, "Female")

        self.assertEqual(stats.students_updated, 1)
        self.assertNotIn("gender", stats.students_fields_filled)

    def test_source_null_field_does_not_clear_target(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice", country="Lesotho")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(result.country, "Lesotho")

    def test_both_null_stays_null(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(Student).filter_by(std_no=100001).one()
            for fname in STUDENT_FILLABLE_FIELDS:
                self.assertIsNone(getattr(result, fname))

        self.assertEqual(stats.students_skipped, 1)

    def test_empty_string_treated_as_null(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", national_id="", country="  ", race="")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertIsNone(result.national_id)
            self.assertIsNone(result.country)
            self.assertIsNone(result.race)

        self.assertEqual(stats.students_skipped, 1)

    def test_new_student_empty_strings_become_null(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", national_id="", country="Lesotho")
            src.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertIsNone(result.national_id)
            self.assertEqual(result.country, "Lesotho")


class TestMergeStudentsMixed(unittest.TestCase):
    def setUp(self) -> None:
        self.source_engine = _create_test_engine()
        self.target_engine = _create_test_engine()

    def tearDown(self) -> None:
        self.source_engine.dispose()
        self.target_engine.dispose()

    def test_mixed_add_update_skip(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "New Student", country="Lesotho")
            _add_student(src, 100002, "Updatable", country="SA")
            _add_student(src, 100003, "Complete")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100002, "Updatable")
            _add_student(tgt, 100003, "Complete", country="Lesotho")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        self.assertEqual(stats.students_added, 1)
        self.assertEqual(stats.students_updated, 1)
        self.assertEqual(stats.students_skipped, 1)

        with Session(self.target_engine) as tgt:
            self.assertEqual(tgt.query(Student).count(), 3)

    def test_target_only_students_preserved(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Source Only")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 200001, "Target Only", country="Lesotho")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            self.assertEqual(tgt.query(Student).count(), 2)
            target_only = tgt.query(Student).filter_by(std_no=200001).one()
            self.assertEqual(target_only.name, "Target Only")
            self.assertEqual(target_only.country, "Lesotho")

    def test_empty_source_no_changes(self) -> None:
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Existing", country="Lesotho")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            self.assertEqual(tgt.query(Student).count(), 1)
            result = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(result.country, "Lesotho")

        self.assertEqual(stats.students_added, 0)
        self.assertEqual(stats.students_updated, 0)

    def test_empty_target(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "A")
            _add_student(src, 100002, "B")
            src.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        self.assertEqual(stats.students_added, 2)
        self.assertEqual(stats.students_updated, 0)


class TestMergeStudentEducation(unittest.TestCase):
    def setUp(self) -> None:
        self.source_engine = _create_test_engine()
        self.target_engine = _create_test_engine()

    def tearDown(self) -> None:
        self.source_engine.dispose()
        self.target_engine.dispose()

    def test_add_new_education(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(
                StudentEducation(
                    std_no=100001,
                    school_name="High School A",
                    type="Secondary",
                    level="LGCSE",
                    cms_id=1001,
                )
            )
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_student_education(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(StudentEducation).filter_by(std_no=100001).one()
            self.assertEqual(result.school_name, "High School A")
            self.assertEqual(result.type, "Secondary")
            self.assertEqual(result.level, "LGCSE")
            self.assertEqual(result.cms_id, 1001)

        self.assertEqual(stats.education_added, 1)

    def test_skip_existing_by_cms_id(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(
                StudentEducation(
                    std_no=100001,
                    school_name="High School A",
                    cms_id=1001,
                )
            )
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.add(
                StudentEducation(
                    std_no=100001,
                    school_name="High School A",
                    cms_id=1001,
                )
            )
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_student_education(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            count = tgt.query(StudentEducation).count()
            self.assertEqual(count, 1)

        self.assertEqual(stats.education_skipped, 1)
        self.assertEqual(stats.education_added, 0)

    def test_skip_education_for_missing_student(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(
                StudentEducation(
                    std_no=100001,
                    school_name="School X",
                    cms_id=2001,
                )
            )
            src.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_student_education(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            count = tgt.query(StudentEducation).count()
            self.assertEqual(count, 0)

        self.assertEqual(stats.education_skipped, 1)

    def test_add_education_without_cms_id(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(
                StudentEducation(
                    std_no=100001,
                    school_name="Unknown School",
                    cms_id=None,
                )
            )
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_student_education(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            count = tgt.query(StudentEducation).count()
            self.assertEqual(count, 1)

        self.assertEqual(stats.education_added, 1)

    def test_multiple_education_records(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(StudentEducation(std_no=100001, school_name="S1", cms_id=1001))
            src.add(StudentEducation(std_no=100001, school_name="S2", cms_id=1002))
            src.add(StudentEducation(std_no=100001, school_name="S3", cms_id=1003))
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.add(StudentEducation(std_no=100001, school_name="S1", cms_id=1001))
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_student_education(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            count = tgt.query(StudentEducation).count()
            self.assertEqual(count, 3)

        self.assertEqual(stats.education_added, 2)
        self.assertEqual(stats.education_skipped, 1)

    def test_preserves_all_fields(self) -> None:
        start = datetime(2015, 1, 1)
        end = datetime(2019, 12, 1)
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(
                StudentEducation(
                    std_no=100001,
                    school_name="Maseru High",
                    type="Secondary",
                    level="LGCSE",
                    start_date=start,
                    end_date=end,
                    cms_id=5001,
                )
            )
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_student_education(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(StudentEducation).filter_by(cms_id=5001).one()
            self.assertEqual(result.std_no, 100001)
            self.assertEqual(result.school_name, "Maseru High")
            self.assertEqual(result.type, "Secondary")
            self.assertEqual(result.level, "LGCSE")
            self.assertEqual(result.start_date, start)
            self.assertEqual(result.end_date, end)

    def test_target_education_preserved(self) -> None:
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.add(
                StudentEducation(
                    std_no=100001,
                    school_name="Target Only School",
                    cms_id=9999,
                )
            )
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_student_education(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(StudentEducation).filter_by(cms_id=9999).one()
            self.assertEqual(result.school_name, "Target Only School")


class TestMergeNextOfKins(unittest.TestCase):
    def setUp(self) -> None:
        self.source_engine = _create_test_engine()
        self.target_engine = _create_test_engine()

    def tearDown(self) -> None:
        self.source_engine.dispose()
        self.target_engine.dispose()

    def test_add_new_kin(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(
                NextOfKin(
                    std_no=100001,
                    name="Jane Mother",
                    relationship="Mother",
                    phone="+266 5000",
                )
            )
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_next_of_kins(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(NextOfKin).filter_by(std_no=100001).one()
            self.assertEqual(result.name, "Jane Mother")
            self.assertEqual(result.relationship, "Mother")
            self.assertEqual(result.phone, "+266 5000")

        self.assertEqual(stats.kins_added, 1)

    def test_skip_existing_kin_same_name(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(NextOfKin(std_no=100001, name="Jane Mother", relationship="Mother"))
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.add(NextOfKin(std_no=100001, name="Jane Mother", relationship="Mother"))
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_next_of_kins(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            count = tgt.query(NextOfKin).count()
            self.assertEqual(count, 1)

        self.assertEqual(stats.kins_skipped, 1)

    def test_skip_kin_for_missing_student(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(NextOfKin(std_no=100001, name="Jane Mother", relationship="Mother"))
            src.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_next_of_kins(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            count = tgt.query(NextOfKin).count()
            self.assertEqual(count, 0)

        self.assertEqual(stats.kins_skipped, 1)

    def test_case_insensitive_name_match(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(NextOfKin(std_no=100001, name="JANE MOTHER", relationship="Mother"))
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.add(NextOfKin(std_no=100001, name="jane mother", relationship="Mother"))
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_next_of_kins(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            count = tgt.query(NextOfKin).count()
            self.assertEqual(count, 1)

        self.assertEqual(stats.kins_skipped, 1)

    def test_whitespace_trimmed_name_match(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(
                NextOfKin(std_no=100001, name="  Jane Mother  ", relationship="Mother")
            )
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.add(NextOfKin(std_no=100001, name="Jane Mother", relationship="Mother"))
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_next_of_kins(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            count = tgt.query(NextOfKin).count()
            self.assertEqual(count, 1)

        self.assertEqual(stats.kins_skipped, 1)

    def test_different_name_same_student_adds(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(NextOfKin(std_no=100001, name="Father Name", relationship="Father"))
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.add(NextOfKin(std_no=100001, name="Mother Name", relationship="Mother"))
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_next_of_kins(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            count = tgt.query(NextOfKin).count()
            self.assertEqual(count, 2)

        self.assertEqual(stats.kins_added, 1)

    def test_multiple_kins_for_student(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(NextOfKin(std_no=100001, name="Mother", relationship="Mother"))
            src.add(NextOfKin(std_no=100001, name="Father", relationship="Father"))
            src.add(NextOfKin(std_no=100001, name="Guardian", relationship="Guardian"))
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.add(NextOfKin(std_no=100001, name="Mother", relationship="Mother"))
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_next_of_kins(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            count = tgt.query(NextOfKin).count()
            self.assertEqual(count, 3)

        self.assertEqual(stats.kins_added, 2)
        self.assertEqual(stats.kins_skipped, 1)

    def test_preserves_all_fields(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(
                NextOfKin(
                    std_no=100001,
                    name="Jane Doe",
                    relationship="Mother",
                    phone="+266 5000",
                    email="jane@test.com",
                    occupation="Teacher",
                    address="123 Main St",
                    country="Lesotho",
                )
            )
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_next_of_kins(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(NextOfKin).filter_by(std_no=100001).one()
            self.assertEqual(result.name, "Jane Doe")
            self.assertEqual(result.relationship, "Mother")
            self.assertEqual(result.phone, "+266 5000")
            self.assertEqual(result.email, "jane@test.com")
            self.assertEqual(result.occupation, "Teacher")
            self.assertEqual(result.address, "123 Main St")
            self.assertEqual(result.country, "Lesotho")

    def test_target_kins_preserved(self) -> None:
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.add(
                NextOfKin(
                    std_no=100001,
                    name="Target Only Kin",
                    relationship="Other",
                    phone="12345",
                )
            )
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_next_of_kins(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            result = tgt.query(NextOfKin).one()
            self.assertEqual(result.name, "Target Only Kin")
            self.assertEqual(result.phone, "12345")

    def test_no_duplicate_kins_from_source(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(NextOfKin(std_no=100001, name="Mother", relationship="Mother"))
            src.add(NextOfKin(std_no=100001, name="Mother", relationship="Mother"))
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_next_of_kins(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            count = tgt.query(NextOfKin).count()
            self.assertEqual(count, 1)

        self.assertEqual(stats.kins_added, 1)
        self.assertEqual(stats.kins_skipped, 1)


class TestRunMergeIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.source_engine = _create_test_engine()
        self.target_engine = _create_test_engine()

    def tearDown(self) -> None:
        self.source_engine.dispose()
        self.target_engine.dispose()

    def test_full_merge(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "New Student", country="Lesotho", race="African")
            _add_student(
                src,
                100002,
                "Existing Student",
                country="SA",
                nationality="South African",
            )
            src.add(StudentEducation(std_no=100001, school_name="S1", cms_id=1001))
            src.add(StudentEducation(std_no=100002, school_name="S2", cms_id=1002))
            src.add(NextOfKin(std_no=100001, name="Kin A", relationship="Mother"))
            src.add(NextOfKin(std_no=100002, name="Kin B", relationship="Father"))
            src.commit()

        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100002, "Existing Student", country="Lesotho")
            tgt.add(StudentEducation(std_no=100002, school_name="S2", cms_id=1002))
            tgt.add(NextOfKin(std_no=100002, name="Kin B", relationship="Father"))
            tgt.commit()

        stats = run_merge(self.source_engine, self.target_engine)

        self.assertEqual(stats.students_added, 1)
        self.assertEqual(stats.students_updated, 1)
        self.assertEqual(stats.education_added, 1)
        self.assertEqual(stats.education_skipped, 1)
        self.assertEqual(stats.kins_added, 1)
        self.assertEqual(stats.kins_skipped, 1)

        with Session(self.target_engine) as tgt:
            self.assertEqual(tgt.query(Student).count(), 2)
            self.assertEqual(tgt.query(StudentEducation).count(), 2)
            self.assertEqual(tgt.query(NextOfKin).count(), 2)

            existing = tgt.query(Student).filter_by(std_no=100002).one()
            self.assertEqual(existing.country, "Lesotho")
            self.assertEqual(existing.nationality, "South African")

    def test_idempotent_merge(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", country="Lesotho")
            src.add(StudentEducation(std_no=100001, school_name="S1", cms_id=1001))
            src.add(NextOfKin(std_no=100001, name="Kin A", relationship="Mother"))
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        stats1 = run_merge(self.source_engine, self.target_engine)
        self.assertEqual(stats1.students_updated, 1)
        self.assertEqual(stats1.education_added, 1)
        self.assertEqual(stats1.kins_added, 1)

        stats2 = run_merge(self.source_engine, self.target_engine)
        self.assertEqual(stats2.students_skipped, 1)
        self.assertEqual(stats2.students_added, 0)
        self.assertEqual(stats2.students_updated, 0)
        self.assertEqual(stats2.education_skipped, 1)
        self.assertEqual(stats2.education_added, 0)
        self.assertEqual(stats2.kins_skipped, 1)
        self.assertEqual(stats2.kins_added, 0)

        with Session(self.target_engine) as tgt:
            self.assertEqual(tgt.query(Student).count(), 1)
            self.assertEqual(tgt.query(StudentEducation).count(), 1)
            self.assertEqual(tgt.query(NextOfKin).count(), 1)

    def test_no_data_loss_on_merge(self) -> None:
        with Session(self.target_engine) as tgt:
            _add_student(
                tgt,
                100001,
                "Original Student",
                status="Active",
                country="Lesotho",
                phone1="+266 111",
                religion="Christian",
            )
            _add_student(tgt, 200001, "Target Only Student", country="SA")
            tgt.add(
                StudentEducation(
                    std_no=100001,
                    school_name="Target School",
                    cms_id=9001,
                )
            )
            tgt.add(
                NextOfKin(
                    std_no=100001,
                    name="Target Kin",
                    relationship="Other",
                    phone="111",
                )
            )
            tgt.commit()

        original_student_count: int
        original_edu_count: int
        original_kin_count: int
        with Session(self.target_engine) as tgt:
            original_student_count = tgt.query(Student).count()
            original_edu_count = tgt.query(StudentEducation).count()
            original_kin_count = tgt.query(NextOfKin).count()

        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Source Student", country="SA", race="African")
            src.add(StudentEducation(std_no=100001, school_name="S1", cms_id=2001))
            src.add(NextOfKin(std_no=100001, name="Src Kin", relationship="Mother"))
            src.commit()

        run_merge(self.source_engine, self.target_engine)

        with Session(self.target_engine) as tgt:
            self.assertGreaterEqual(tgt.query(Student).count(), original_student_count)
            self.assertGreaterEqual(
                tgt.query(StudentEducation).count(), original_edu_count
            )
            self.assertGreaterEqual(tgt.query(NextOfKin).count(), original_kin_count)

            s = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(s.name, "Original Student")
            self.assertEqual(s.country, "Lesotho")
            self.assertEqual(s.phone1, "+266 111")
            self.assertEqual(s.religion, "Christian")
            self.assertEqual(s.race, "African")

            target_only = tgt.query(Student).filter_by(std_no=200001).one()
            self.assertEqual(target_only.name, "Target Only Student")
            self.assertEqual(target_only.country, "SA")

            target_edu = tgt.query(StudentEducation).filter_by(cms_id=9001).one()
            self.assertEqual(target_edu.school_name, "Target School")

            target_kin = tgt.query(NextOfKin).filter_by(name="Target Kin").one()
            self.assertEqual(target_kin.phone, "111")

    def test_rollback_on_error(self) -> None:
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Existing", country="Lesotho")
            tgt.commit()

        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Source", race="African")
            src.commit()

        stats = run_merge(self.source_engine, self.target_engine)

        with Session(self.target_engine) as tgt:
            s = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(s.country, "Lesotho")
            self.assertEqual(s.race, "African")

    def test_new_students_get_kins_and_education(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "New Student", country="Lesotho")
            src.add(StudentEducation(std_no=100001, school_name="S1", cms_id=3001))
            src.add(NextOfKin(std_no=100001, name="Mom", relationship="Mother"))
            src.commit()

        stats = run_merge(self.source_engine, self.target_engine)

        self.assertEqual(stats.students_added, 1)
        self.assertEqual(stats.education_added, 1)
        self.assertEqual(stats.kins_added, 1)

        with Session(self.target_engine) as tgt:
            s = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(s.country, "Lesotho")

            edu = tgt.query(StudentEducation).filter_by(std_no=100001).one()
            self.assertEqual(edu.school_name, "S1")

            kin = tgt.query(NextOfKin).filter_by(std_no=100001).one()
            self.assertEqual(kin.name, "Mom")

    def test_progress_callback_called(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(StudentEducation(std_no=100001, school_name="S1", cms_id=1001))
            src.add(NextOfKin(std_no=100001, name="Kin", relationship="Mother"))
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        calls: list[tuple[str, int, int]] = []

        def callback(msg: str, current: int, total: int) -> None:
            calls.append((msg, current, total))

        run_merge(self.source_engine, self.target_engine, callback)
        self.assertGreater(len(calls), 0)
        for msg, current, total in calls:
            self.assertIsInstance(msg, str)
            self.assertGreater(current, 0)
            self.assertGreater(total, 0)
            self.assertLessEqual(current, total)

    def test_large_batch(self) -> None:
        with Session(self.source_engine) as src:
            for i in range(100):
                _add_student(src, 100000 + i, f"Student {i}", country="Lesotho")
                src.add(
                    StudentEducation(
                        std_no=100000 + i,
                        school_name=f"School {i}",
                        cms_id=5000 + i,
                    )
                )
                src.add(
                    NextOfKin(
                        std_no=100000 + i,
                        name=f"Kin {i}",
                        relationship="Mother",
                    )
                )
            src.commit()

        with Session(self.target_engine) as tgt:
            for i in range(50):
                _add_student(tgt, 100000 + i, f"Student {i}")
            tgt.commit()

        stats = run_merge(self.source_engine, self.target_engine)

        self.assertEqual(stats.students_added, 50)
        self.assertEqual(stats.students_updated, 50)

        with Session(self.target_engine) as tgt:
            self.assertEqual(tgt.query(Student).count(), 100)
            self.assertEqual(tgt.query(StudentEducation).count(), 100)
            self.assertEqual(tgt.query(NextOfKin).count(), 100)
            for i in range(100):
                s = tgt.query(Student).filter_by(std_no=100000 + i).one()
                self.assertEqual(s.country, "Lesotho")


class TestMergeStatsSummary(unittest.TestCase):
    def test_summary_format(self) -> None:
        stats = MergeStats(
            students_added=10,
            students_updated=20,
            students_skipped=5,
            students_fields_filled={"country": 15, "race": 12},
            education_added=50,
            education_skipped=10,
            kins_added=100,
            kins_skipped=20,
        )
        summary = stats.summary()
        self.assertIn("10 added", summary)
        self.assertIn("20 updated", summary)
        self.assertIn("5 skipped", summary)
        self.assertIn("country: 15", summary)
        self.assertIn("race: 12", summary)
        self.assertIn("50 added", summary)
        self.assertIn("100 added", summary)


if __name__ == "__main__":
    unittest.main()


class TestAnalyzeDifferences(unittest.TestCase):
    def setUp(self) -> None:
        self.source_engine = _create_test_engine()
        self.target_engine = _create_test_engine()

    def tearDown(self) -> None:
        self.source_engine.dispose()
        self.target_engine.dispose()

    def test_counts_students_to_add(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            _add_student(src, 100002, "Bob")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        result = analyze_differences(self.source_engine, self.target_engine)
        self.assertEqual(result.students_to_add, 1)

    def test_counts_fields_to_fill(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", country="Lesotho", gender="Female")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        result = analyze_differences(self.source_engine, self.target_engine)
        self.assertEqual(result.fields_to_fill.get("country"), 1)
        self.assertEqual(result.fields_to_fill.get("gender"), 1)
        self.assertEqual(result.students_to_update, 1)

    def test_detects_conflicts(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", country="Lesotho")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice", country="South Africa")
            tgt.commit()

        result = analyze_differences(self.source_engine, self.target_engine)
        self.assertEqual(len(result.conflicts), 1)
        self.assertEqual(result.conflicts[0].field_name, "country")
        self.assertEqual(result.conflicts[0].target_value, "South Africa")
        self.assertEqual(result.conflicts[0].source_value, "Lesotho")

    def test_no_conflict_when_values_match(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", country="Lesotho")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice", country="Lesotho")
            tgt.commit()

        result = analyze_differences(self.source_engine, self.target_engine)
        self.assertEqual(len(result.conflicts), 0)

    def test_counts_education_to_add(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(StudentEducation(std_no=100001, school_name="School A", cms_id=999))
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        result = analyze_differences(self.source_engine, self.target_engine)
        self.assertEqual(result.education_to_add, 1)

    def test_counts_kins_to_add(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(NextOfKin(std_no=100001, name="John Doe", relationship="Parent"))
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        result = analyze_differences(self.source_engine, self.target_engine)
        self.assertEqual(result.kins_to_add, 1)

    def test_no_kin_to_add_when_exists(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice")
            src.add(NextOfKin(std_no=100001, name="John Doe", relationship="Parent"))
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.add(NextOfKin(std_no=100001, name="John Doe", relationship="Parent"))
            tgt.commit()

        result = analyze_differences(self.source_engine, self.target_engine)
        self.assertEqual(result.kins_to_add, 0)

    def test_empty_source(self) -> None:
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice")
            tgt.commit()

        result = analyze_differences(self.source_engine, self.target_engine)
        self.assertEqual(result.students_to_add, 0)
        self.assertEqual(result.students_to_update, 0)
        self.assertEqual(len(result.conflicts), 0)

    def test_multiple_conflicts_per_student(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", country="Lesotho", nationality="Mosotho")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(
                tgt, 100001, "Alice", country="South Africa", nationality="Zulu"
            )
            tgt.commit()

        result = analyze_differences(self.source_engine, self.target_engine)
        self.assertEqual(len(result.conflicts), 2)
        field_names = {c.field_name for c in result.conflicts}
        self.assertIn("country", field_names)
        self.assertIn("nationality", field_names)


class TestMergeStudentsWithResolutions(unittest.TestCase):
    def setUp(self) -> None:
        self.source_engine = _create_test_engine()
        self.target_engine = _create_test_engine()

    def tearDown(self) -> None:
        self.source_engine.dispose()
        self.target_engine.dispose()

    def test_resolution_applies_source_value(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", country="Lesotho")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice", country="South Africa")
            tgt.commit()

        resolutions = {(100001, "country"): "Lesotho"}
        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats, resolutions=resolutions)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            s = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(s.country, "Lesotho")
        self.assertEqual(stats.students_updated, 1)

    def test_no_resolution_keeps_registry(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", country="Lesotho")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice", country="South Africa")
            tgt.commit()

        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            s = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(s.country, "South Africa")
        self.assertEqual(stats.students_skipped, 1)

    def test_resolution_same_as_target_no_change(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", country="Lesotho")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice", country="South Africa")
            tgt.commit()

        resolutions = {(100001, "country"): "South Africa"}
        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats, resolutions=resolutions)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            s = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(s.country, "South Africa")
        self.assertEqual(stats.students_skipped, 1)

    def test_resolution_with_national_id_conflict(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", national_id="SRC123")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice", national_id="TGT456")
            tgt.commit()

        resolutions = {(100001, "national_id"): "SRC123"}
        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats, resolutions=resolutions)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            s = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(s.national_id, "SRC123")

    def test_resolution_national_id_skip_if_used(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", national_id="SHARED")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice", national_id="OLD_ID")
            _add_student(tgt, 100002, "Bob", national_id="SHARED")
            tgt.commit()

        resolutions = {(100001, "national_id"): "SHARED"}
        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats, resolutions=resolutions)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            s = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(s.national_id, "OLD_ID")

    def test_mixed_fills_and_resolutions(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(
                src,
                100001,
                "Alice",
                country="Lesotho",
                gender="Female",
                nationality="Mosotho",
            )
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice", country="South Africa")
            tgt.commit()

        resolutions = {(100001, "country"): "Lesotho"}
        stats = MergeStats()
        with Session(self.source_engine) as src, Session(self.target_engine) as tgt:
            merge_students(src, tgt, stats, resolutions=resolutions)
            tgt.commit()

        with Session(self.target_engine) as tgt:
            s = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(s.country, "Lesotho")
            self.assertEqual(s.gender, "Female")
            self.assertEqual(s.nationality, "Mosotho")
        self.assertEqual(stats.students_updated, 1)
        self.assertEqual(stats.students_fields_filled.get("gender"), 1)
        self.assertEqual(stats.students_fields_filled.get("nationality"), 1)

    def test_run_merge_with_resolutions(self) -> None:
        with Session(self.source_engine) as src:
            _add_student(src, 100001, "Alice", country="Lesotho")
            src.commit()
        with Session(self.target_engine) as tgt:
            _add_student(tgt, 100001, "Alice", country="South Africa")
            tgt.commit()

        resolutions = {(100001, "country"): "Lesotho"}
        stats = run_merge(
            self.source_engine,
            self.target_engine,
            resolutions=resolutions,
        )

        with Session(self.target_engine) as tgt:
            s = tgt.query(Student).filter_by(std_no=100001).one()
            self.assertEqual(s.country, "Lesotho")
        self.assertEqual(stats.students_updated, 1)
