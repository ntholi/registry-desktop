import unittest
from unittest.mock import Mock, patch

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


if __name__ == "__main__":
    unittest.main()
