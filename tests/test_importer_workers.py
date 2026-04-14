import unittest
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database import (
    Module,
    NextOfKin,
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
    Term,
)
from features.sync.students.repository import StudentRepository
from features.sync.students.service import StudentSyncService
from features.sync.students.view.importer.importer_project import (
    ImporterProject,
    ImporterProjectManager,
)
from features.sync.students.view.importer.importer_worker import (
    ImporterRetryWorker,
    ImporterWorker,
)


def _project() -> ImporterProject:
    return ImporterProject(
        start_student="901000001",
        end_student="901000003",
        current_student="901000002",
        import_options={
            "student_info": True,
            "personal_info": True,
            "education_history": True,
            "enrollment_data": True,
        },
        status="paused",
        success_count=0,
        failed_count=1,
        failed_students=["901000001"],
    )


class ImporterProjectManagerTests(unittest.TestCase):
    def test_project_normalizes_failed_students(self):
        project = ImporterProject(
            start_student="901000001",
            end_student="901000003",
            current_student="901000001",
            import_options={},
            status="paused",
            failed_count=3,
            failed_students=["901000001", "901000001", "901000002"],
        )

        self.assertEqual(project.failed_students, ["901000001", "901000002"])
        self.assertEqual(project.failed_count, 2)

    def test_resolve_failed_student_moves_student_to_success(self):
        project = _project()

        resolved = ImporterProjectManager.resolve_failed_student(project, "901000001")

        self.assertTrue(resolved)
        self.assertEqual(project.success_count, 1)
        self.assertEqual(project.failed_count, 0)
        self.assertEqual(project.failed_students, [])

    def test_count_remaining_students_uses_numeric_range_without_list_generation(self):
        project = ImporterProject(
            start_student="901000001",
            end_student="901000600",
            current_student="901000450",
            import_options={},
            status="paused",
        )

        self.assertEqual(
            ImporterProjectManager.count_students("901000001", "901000600"),
            600,
        )
        self.assertEqual(
            ImporterProjectManager.count_remaining_students(project),
            151,
        )


class ImporterWorkerTests(unittest.TestCase):
    def test_worker_processes_large_batch_of_600_students(self):
        project = ImporterProject(
            start_student="901000001",
            end_student="901000600",
            current_student="901000001",
            import_options={
                "student_info": True,
                "personal_info": True,
                "education_history": True,
                "enrollment_data": True,
                "addresses": True,
            },
            status="pending",
        )
        callback = Mock()
        sync_service = Mock()

        def fetch_student(std_no, progress_callback, import_options, missing_sponsor):
            progress_callback(f"Fetching {std_no}", 1, 3)
            progress_callback(f"Syncing {std_no}", 2, 3)
            progress_callback(f"Completed {std_no}", 3, 3)
            return int(std_no) % 75 != 0

        sync_service.fetch_student.side_effect = fetch_student

        with patch.object(ImporterProjectManager, "save_project"):
            worker = ImporterWorker(project, sync_service, callback)
            worker.run()

        self.assertEqual(project.status, "completed")
        self.assertEqual(sync_service.fetch_student.call_count, 600)
        self.assertEqual(project.success_count, 592)
        self.assertEqual(project.failed_count, 8)
        failed_students = project.failed_students
        assert failed_students is not None
        self.assertEqual(len(failed_students), 8)
        self.assertEqual(callback.call_args_list[-1].args[0], "finished")

    def test_worker_resume_starts_from_saved_student(self):
        project = ImporterProject(
            start_student="901000001",
            end_student="901000600",
            current_student="901000450",
            import_options={
                "student_info": True,
                "personal_info": True,
                "education_history": True,
                "enrollment_data": True,
                "addresses": True,
            },
            status="paused",
            success_count=449,
        )
        callback = Mock()
        sync_service = Mock()
        processed: list[str] = []

        def fetch_student(std_no, progress_callback, import_options, missing_sponsor):
            processed.append(std_no)
            return True

        sync_service.fetch_student.side_effect = fetch_student

        with patch.object(ImporterProjectManager, "save_project"):
            worker = ImporterWorker(project, sync_service, callback)
            worker.run()

        self.assertEqual(processed[0], "901000450")
        self.assertEqual(len(processed), 151)
        self.assertEqual(project.success_count, 600)
        self.assertEqual(project.failed_count, 0)

    def test_worker_stop_moves_current_student_to_next_student(self):
        project = ImporterProject(
            start_student="901000001",
            end_student="901000600",
            current_student="901000001",
            import_options={
                "student_info": True,
                "personal_info": True,
                "education_history": True,
                "enrollment_data": True,
                "addresses": True,
            },
            status="pending",
        )
        callback = Mock()
        sync_service = Mock()
        processed: list[str] = []
        worker_holder: dict[str, ImporterWorker] = {}

        def fetch_student(std_no, progress_callback, import_options, missing_sponsor):
            processed.append(std_no)
            if len(processed) == 5:
                worker_holder["worker"].stop()
            return True

        sync_service.fetch_student.side_effect = fetch_student

        with patch.object(ImporterProjectManager, "save_project"):
            worker_holder["worker"] = ImporterWorker(project, sync_service, callback)
            worker_holder["worker"].run()

        self.assertEqual(processed, [f"90100000{i}" for i in range(1, 10)][:5])
        self.assertEqual(project.status, "paused")
        self.assertEqual(project.current_student, "901000006")
        self.assertEqual(project.success_count, 5)
        self.assertEqual(callback.call_args_list[-1].args[0], "stopped")


class ImporterRetryWorkerTests(unittest.TestCase):
    def test_retry_worker_removes_student_from_failed_list_on_success(self):
        project = _project()
        sync_service = Mock()
        sync_service.fetch_student.return_value = True
        callback = Mock()

        with patch.object(ImporterProjectManager, "save_project"):
            worker = ImporterRetryWorker(
                project,
                "901000001",
                sync_service,
                callback,
            )
            worker.run()

        self.assertEqual(project.success_count, 1)
        self.assertEqual(project.failed_count, 0)
        self.assertEqual(project.failed_students, [])
        self.assertEqual(callback.call_args_list[-1].args[0], "retry_finished")
        self.assertTrue(callback.call_args_list[-1].args[3])

    def test_retry_worker_keeps_failed_student_when_retry_fails(self):
        project = _project()
        sync_service = Mock()
        sync_service.fetch_student.return_value = False
        callback = Mock()

        with patch.object(ImporterProjectManager, "save_project"):
            worker = ImporterRetryWorker(
                project,
                "901000001",
                sync_service,
                callback,
            )
            worker.run()

        self.assertEqual(project.success_count, 0)
        self.assertEqual(project.failed_count, 1)
        self.assertEqual(project.failed_students, ["901000001"])
        self.assertEqual(callback.call_args_list[-1].args[0], "retry_finished")
        self.assertFalse(callback.call_args_list[-1].args[3])


class StudentSyncServiceTests(unittest.TestCase):
    def test_fetch_student_returns_false_when_selected_sections_have_no_data(self):
        repository = Mock()
        repository.get_active_term_code.return_value = None

        with (
            patch("features.sync.students.service.Browser"),
            patch(
                "features.sync.students.service.scrape_student_view",
                return_value={},
            ),
            patch(
                "features.sync.students.service.scrape_student_personal_view",
                return_value={},
            ),
            patch(
                "features.sync.students.service.extract_student_education_ids",
                return_value=[],
            ),
            patch(
                "features.sync.students.service.scrape_student_addresses",
                return_value=[],
            ),
            patch(
                "features.sync.students.service.extract_student_program_ids",
                return_value=[],
            ),
        ):
            service = StudentSyncService(repository)
            was_updated = service.fetch_student(
                "901000001",
                lambda *_: None,
                {
                    "student_info": True,
                    "personal_info": True,
                    "education_history": True,
                    "addresses": True,
                    "enrollment_data": True,
                    "skip_active_term": False,
                    "delete_programs_before_import": False,
                },
            )

        self.assertFalse(was_updated)
        repository.update_student.assert_not_called()

    def test_fetch_student_returns_false_when_student_info_fails_but_programs_sync(
        self,
    ):
        repository = Mock()
        repository.get_active_term_code.return_value = None
        repository.upsert_student_program.return_value = (
            True,
            "Student program updated",
            321,
        )
        repository.resolve_student_program_structure_id.return_value = None

        with (
            patch("features.sync.students.service.Browser"),
            patch(
                "features.sync.students.service.scrape_student_view",
                return_value={},
            ),
            patch(
                "features.sync.students.service.extract_student_program_ids",
                return_value=[111],
            ),
            patch(
                "features.sync.students.service.scrape_student_program_data",
                return_value={
                    "std_no": "901000001",
                    "program_code": "BIO",
                    "structure_code": "2026-A",
                },
            ),
            patch(
                "features.sync.students.service.extract_student_semester_ids",
                return_value=[],
            ),
        ):
            service = StudentSyncService(repository)
            was_updated = service.fetch_student(
                "901000001",
                lambda *_: None,
                {
                    "student_info": True,
                    "personal_info": False,
                    "education_history": False,
                    "addresses": False,
                    "enrollment_data": True,
                    "skip_active_term": False,
                    "delete_programs_before_import": False,
                },
            )

        self.assertFalse(was_updated)
        repository.upsert_student_program.assert_called_once()

    def test_fetch_student_returns_success_for_addresses_only_import(self):
        repository = Mock()
        repository.get_active_term_code.return_value = None
        repository.update_student.return_value = True
        repository.upsert_next_of_kin.return_value = (True, "Saved")

        with (
            patch("features.sync.students.service.Browser"),
            patch(
                "features.sync.students.service.scrape_student_addresses",
                return_value=[
                    {
                        "name": "Test Guardian",
                        "relationship": "Guardian",
                        "phone": "+26650000000",
                    }
                ],
            ),
        ):
            service = StudentSyncService(repository)
            was_updated = service.fetch_student(
                "901000001",
                lambda *_: None,
                {
                    "student_info": False,
                    "personal_info": False,
                    "education_history": False,
                    "addresses": True,
                    "enrollment_data": False,
                    "skip_active_term": False,
                    "delete_programs_before_import": False,
                },
            )

        self.assertTrue(was_updated)
        repository.update_student.assert_called_once_with("901000001", {})
        repository.upsert_next_of_kin.assert_called_once()

    def test_fetch_student_allows_empty_personal_info_when_other_data_syncs(self):
        repository = Mock()
        repository.get_active_term_code.return_value = None
        repository.update_student.return_value = True
        repository.resolve_student_program_structure_id.return_value = None
        repository.upsert_student_program.return_value = (
            True,
            "Student program updated",
            321,
        )

        with (
            patch("features.sync.students.service.Browser"),
            patch(
                "features.sync.students.service.scrape_student_view",
                return_value={"name": "Thobekile Ramonono"},
            ),
            patch(
                "features.sync.students.service.scrape_student_personal_view",
                return_value={},
            ),
            patch(
                "features.sync.students.service.extract_student_program_ids",
                return_value=[111],
            ),
            patch(
                "features.sync.students.service.scrape_student_program_data",
                return_value={
                    "std_no": "901000001",
                    "program_code": "BIO",
                    "structure_code": "2026-A",
                },
            ),
            patch(
                "features.sync.students.service.extract_student_semester_ids",
                return_value=[],
            ),
        ):
            service = StudentSyncService(repository)
            was_updated = service.fetch_student(
                "901000001",
                lambda *_: None,
                {
                    "student_info": True,
                    "personal_info": True,
                    "education_history": False,
                    "addresses": False,
                    "enrollment_data": True,
                    "skip_active_term": False,
                    "delete_programs_before_import": False,
                },
            )

        self.assertTrue(was_updated)

    def test_fetch_student_returns_success_for_enrollment_only_import(self):
        repository = Mock()
        repository.get_active_term_code.return_value = None
        repository.resolve_student_program_structure_id.return_value = None
        repository.upsert_student_program.return_value = (
            True,
            "Student program updated",
            321,
        )
        service = None

        with (
            patch("features.sync.students.service.Browser"),
            patch(
                "features.sync.students.service.extract_student_program_ids",
                return_value=[111],
            ),
            patch(
                "features.sync.students.service.scrape_student_program_data",
                return_value={
                    "std_no": "901000001",
                    "program_code": "BIO",
                    "structure_code": "2026-A",
                },
            ),
            patch(
                "features.sync.students.service.extract_student_semester_ids",
                return_value=[],
            ),
        ):
            service = StudentSyncService(repository)
            was_updated = service.fetch_student(
                "901000001",
                lambda *_: None,
                {
                    "student_info": False,
                    "personal_info": False,
                    "education_history": False,
                    "addresses": False,
                    "enrollment_data": True,
                    "skip_active_term": False,
                    "delete_programs_before_import": False,
                },
            )

        self.assertTrue(was_updated)
        repository.update_student.assert_not_called()
        repository.upsert_student_program.assert_called_once_with(
            111,
            "901000001",
            {
                "std_no": "901000001",
                "program_code": "BIO",
                "structure_code": "2026-A",
            },
        )

    def test_fetch_student_uses_term_fallback_when_structure_code_missing(self):
        repository = Mock()
        repository.get_active_term_code.return_value = None
        repository.resolve_student_program_structure_id.return_value = 44
        repository.upsert_student_program.return_value = (
            True,
            "Student program updated",
            321,
        )

        with (
            patch("features.sync.students.service.Browser"),
            patch(
                "features.sync.students.service.extract_student_program_ids",
                return_value=[111],
            ),
            patch(
                "features.sync.students.service.scrape_student_program_data",
                return_value={
                    "std_no": "901000001",
                    "program_code": "INT",
                    "start_term": "2009-07",
                    "reg_date": "2009-09-17",
                },
            ),
            patch(
                "features.sync.students.service.extract_student_semester_ids",
                return_value=[],
            ),
        ):
            service = StudentSyncService(repository)
            was_updated = service.fetch_student(
                "901000001",
                lambda *_: None,
                {
                    "student_info": False,
                    "personal_info": False,
                    "education_history": False,
                    "addresses": False,
                    "enrollment_data": True,
                    "skip_active_term": False,
                    "delete_programs_before_import": False,
                },
            )

        self.assertTrue(was_updated)
        repository.resolve_student_program_structure_id.assert_called_once_with(
            "INT",
            None,
            "2009-07",
            None,
            "2009-09-17",
        )

    def test_fetch_student_returns_false_when_education_scrape_returns_incomplete_data(
        self,
    ):
        repository = Mock()
        repository.get_active_term_code.return_value = None

        with (
            patch("features.sync.students.service.Browser"),
            patch(
                "features.sync.students.service.extract_student_education_ids",
                return_value=[701],
            ),
            patch(
                "features.sync.students.service.scrape_student_education_data",
                return_value={},
            ),
        ):
            service = StudentSyncService(repository)
            was_updated = service.fetch_student(
                "901000001",
                lambda *_: None,
                {
                    "student_info": False,
                    "personal_info": False,
                    "education_history": True,
                    "addresses": False,
                    "enrollment_data": False,
                    "skip_active_term": False,
                    "delete_programs_before_import": False,
                },
            )

        self.assertFalse(was_updated)
        repository.upsert_student_education.assert_not_called()

    def test_fetch_student_returns_false_when_program_scrape_returns_incomplete_data(
        self,
    ):
        repository = Mock()
        repository.get_active_term_code.return_value = None

        with (
            patch("features.sync.students.service.Browser"),
            patch(
                "features.sync.students.service.extract_student_program_ids",
                return_value=[111],
            ),
            patch(
                "features.sync.students.service.scrape_student_program_data",
                return_value={},
            ),
        ):
            service = StudentSyncService(repository)
            was_updated = service.fetch_student(
                "901000001",
                lambda *_: None,
                {
                    "student_info": False,
                    "personal_info": False,
                    "education_history": False,
                    "addresses": False,
                    "enrollment_data": True,
                    "skip_active_term": False,
                    "delete_programs_before_import": False,
                },
            )

        self.assertFalse(was_updated)
        repository.upsert_student_program.assert_not_called()

    def test_fetch_student_returns_false_when_semester_scrape_returns_incomplete_data(
        self,
    ):
        repository = Mock()
        repository.get_active_term_code.return_value = None
        repository.resolve_student_program_structure_id.return_value = 44
        repository.upsert_student_program.return_value = (
            True,
            "Student program updated",
            321,
        )

        with (
            patch("features.sync.students.service.Browser"),
            patch(
                "features.sync.students.service.extract_student_program_ids",
                return_value=[111],
            ),
            patch(
                "features.sync.students.service.scrape_student_program_data",
                return_value={
                    "std_no": "901000001",
                    "program_code": "BIO",
                    "structure_code": "2026-A",
                },
            ),
            patch(
                "features.sync.students.service.extract_student_semester_ids",
                return_value=[222],
            ),
            patch(
                "features.sync.students.service.scrape_student_semester_data",
                return_value={},
            ),
        ):
            service = StudentSyncService(repository)
            was_updated = service.fetch_student(
                "901000001",
                lambda *_: None,
                {
                    "student_info": False,
                    "personal_info": False,
                    "education_history": False,
                    "addresses": False,
                    "enrollment_data": True,
                    "skip_active_term": False,
                    "delete_programs_before_import": False,
                },
            )

        self.assertFalse(was_updated)
        repository.upsert_student_semester.assert_not_called()

    def test_fetch_student_returns_false_when_module_scrape_raises(self):
        repository = Mock()
        repository.get_active_term_code.return_value = None
        repository.resolve_student_program_structure_id.return_value = 44
        repository.upsert_student_program.return_value = (
            True,
            "Student program updated",
            321,
        )
        repository.upsert_student_semester.return_value = (
            True,
            "Student semester updated",
            654,
        )

        with (
            patch("features.sync.students.service.Browser"),
            patch(
                "features.sync.students.service.extract_student_program_ids",
                return_value=[111],
            ),
            patch(
                "features.sync.students.service.scrape_student_program_data",
                return_value={
                    "std_no": "901000001",
                    "program_code": "BIO",
                    "structure_code": "2026-A",
                },
            ),
            patch(
                "features.sync.students.service.extract_student_semester_ids",
                return_value=[222],
            ),
            patch(
                "features.sync.students.service.scrape_student_semester_data",
                return_value={
                    "cms_id": 222,
                    "term": "2026-01",
                    "structure_semester_id": 44,
                    "status": "Active",
                },
            ),
            patch(
                "features.sync.students.service.scrape_student_modules_concurrent",
                side_effect=RuntimeError("module scrape failed"),
            ),
        ):
            service = StudentSyncService(repository)
            was_updated = service.fetch_student(
                "901000001",
                lambda *_: None,
                {
                    "student_info": False,
                    "personal_info": False,
                    "education_history": False,
                    "addresses": False,
                    "enrollment_data": True,
                    "skip_active_term": False,
                    "delete_programs_before_import": False,
                },
            )

        self.assertFalse(was_updated)
        repository.upsert_student_module.assert_not_called()


class ImporterDatabaseBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.browser_patcher = patch("features.sync.students.service.Browser")
        cls.browser_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.browser_patcher.stop()

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
            NextOfKin.__table__,
            StudentEducation.__table__,
            Term.__table__,
            Sponsor.__table__,
        ]:
            table.create(self.engine)

        self.repository = StudentRepository()
        self.repository._engine = self.engine
        self.repository.clear_structure_semester_cache()
        self.repository.clear_sponsor_cache()

        with Session(self.engine) as session:
            school = School(code="BUS", name="Business", cms_id=1)
            session.add(school)
            session.flush()

            program = Program(
                code="BBIB",
                name="International Business",
                level="degree",
                school_id=school.id,
                cms_id=10,
            )
            session.add(program)
            session.flush()

            structure = Structure(
                code="2026-A",
                desc="2026-A",
                program_id=program.id,
                cms_id=20,
            )
            session.add(structure)
            session.flush()

            structure_semester = StructureSemester(
                structure_id=structure.id,
                semester_number="01",
                name="Semester 1",
                total_credits=12.0,
                cms_id=30,
            )
            session.add(structure_semester)
            session.flush()

            module = Module(
                code="ACC101",
                name="Accounting Fundamentals",
                status="Active",
                cms_id=40,
            )
            session.add(module)
            session.flush()

            semester_module = SemesterModule(
                module_id=module.id,
                type="Core",
                credits=12.0,
                semester_id=structure_semester.id,
                cms_id=50,
            )
            session.add(semester_module)
            session.commit()

            self.structure_semester_id = structure_semester.id

    def tearDown(self):
        self.repository.clear_structure_semester_cache()
        self.repository.clear_sponsor_cache()
        self.engine.dispose()

    def test_importer_worker_persists_complete_600_student_batch(self):
        service = StudentSyncService(self.repository)
        callback = Mock()
        project = ImporterProject(
            start_student="901000001",
            end_student="901000600",
            current_student="901000001",
            import_options={
                "student_info": True,
                "personal_info": True,
                "education_history": True,
                "enrollment_data": True,
                "addresses": True,
                "skip_active_term": False,
                "delete_programs_before_import": False,
            },
            status="pending",
        )

        def scrape_student_view(std_no):
            return {
                "name": f"Student {std_no}",
                "national_id": f"ID{std_no}",
                "phone1": f"+266{std_no[-8:]}",
                "status": "Active",
            }

        def scrape_student_personal_view(std_no):
            return {
                "date_of_birth": "2001-02-03",
                "gender": "Male" if int(std_no) % 2 else "Female",
                "marital_status": "Single",
                "religion": "Christian",
                "nationality": "Lesotho",
            }

        def extract_student_education_ids(std_no):
            return [int(std_no)]

        def scrape_student_education_data(education_id):
            return {
                "cms_id": int(education_id),
                "std_no": str(education_id),
                "school_name": "Maseru High",
                "type": "Secondary",
                "level": "LGCSE",
                "end_date": "2019-11-01",
            }

        def scrape_student_addresses(std_no):
            return [
                {
                    "name": f"Guardian {std_no}",
                    "relationship": "Guardian",
                    "phone": f"+2665{std_no[-7:]}",
                    "address": "Maseru",
                    "country": "Lesotho",
                }
            ]

        def extract_student_program_ids(std_no):
            return [f"{std_no}11"]

        def scrape_student_program_data(program_id):
            std_no = program_id[:-2]
            return {
                "std_no": int(std_no),
                "program_code": "BBIB",
                "structure_code": "2026-A",
                "status": "Active",
                "start_term": "2026-01",
                "intake_date": "2026-01-01",
            }

        def extract_student_semester_ids(program_id):
            return [f"{program_id}22"]

        def scrape_student_semester_data(
            semester_id, structure_id, repository, resolve_missing_sponsor
        ):
            return {
                "cms_id": int(semester_id),
                "term": "2026-01",
                "structure_semester_id": self.structure_semester_id,
                "status": "Active",
                "caf_date": "2026-02-01",
            }

        def scrape_student_modules_concurrent(semester_id, student_semester_db_id):
            return [
                {
                    "cms_id": int(f"{semester_id}33"),
                    "student_semester_db_id": student_semester_db_id,
                    "semester_module_cms_id": 50,
                    "module_code": "ACC101",
                    "module_name": "Accounting Fundamentals",
                    "type": "Core",
                    "credits": 12.0,
                    "status": "Compulsory",
                    "marks": "78",
                    "grade": "B+",
                }
            ]

        with (
            patch(
                "features.sync.students.service.scrape_student_view",
                side_effect=scrape_student_view,
            ),
            patch(
                "features.sync.students.service.scrape_student_personal_view",
                side_effect=scrape_student_personal_view,
            ),
            patch(
                "features.sync.students.service.extract_student_education_ids",
                side_effect=extract_student_education_ids,
            ),
            patch(
                "features.sync.students.service.scrape_student_education_data",
                side_effect=scrape_student_education_data,
            ),
            patch(
                "features.sync.students.service.scrape_student_addresses",
                side_effect=scrape_student_addresses,
            ),
            patch(
                "features.sync.students.service.extract_student_program_ids",
                side_effect=extract_student_program_ids,
            ),
            patch(
                "features.sync.students.service.scrape_student_program_data",
                side_effect=scrape_student_program_data,
            ),
            patch(
                "features.sync.students.service.extract_student_semester_ids",
                side_effect=extract_student_semester_ids,
            ),
            patch(
                "features.sync.students.service.scrape_student_semester_data",
                side_effect=scrape_student_semester_data,
            ),
            patch(
                "features.sync.students.service.scrape_student_modules_concurrent",
                side_effect=scrape_student_modules_concurrent,
            ),
            patch.object(ImporterProjectManager, "save_project"),
        ):
            worker = ImporterWorker(project, service, callback)
            worker.run()

        self.assertEqual(project.status, "completed")
        self.assertEqual(project.success_count, 600)
        self.assertEqual(project.failed_count, 0)
        self.assertEqual(callback.call_args_list[-1].args[0], "finished")

        with Session(self.engine) as session:
            self.assertEqual(session.query(Student).count(), 600)
            self.assertEqual(session.query(StudentEducation).count(), 600)
            self.assertEqual(session.query(NextOfKin).count(), 600)
            self.assertEqual(session.query(StudentProgram).count(), 600)
            self.assertEqual(session.query(StudentSemester).count(), 600)
            self.assertEqual(session.query(StudentModule).count(), 600)

            student = session.query(Student).filter(Student.std_no == 901000001).one()
            semester = (
                session.query(StudentSemester)
                .join(
                    StudentProgram,
                    StudentSemester.student_program_id == StudentProgram.id,
                )
                .filter(StudentProgram.std_no == 901000001)
                .one()
            )
            student_module = (
                session.query(StudentModule)
                .filter(StudentModule.student_semester_id == semester.id)
                .one()
            )

        self.assertEqual(student.name, "Student 901000001")
        self.assertEqual(student.national_id, "ID901000001")
        self.assertEqual(student.gender, "Male")
        date_of_birth = student.date_of_birth
        assert date_of_birth is not None
        self.assertEqual(date_of_birth.isoformat(), "2001-02-03T00:00:00")
        self.assertEqual(student_module.grade, "B+")
        self.assertEqual(student_module.status, "Compulsory")


if __name__ == "__main__":
    unittest.main()
