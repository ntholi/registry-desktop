import unittest
from unittest.mock import Mock, patch

from features.sync.students.view.importer.importer_project import (
    ImporterProject,
    ImporterProjectManager,
)
from features.sync.students.view.importer.importer_worker import ImporterRetryWorker


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


if __name__ == "__main__":
    unittest.main()
