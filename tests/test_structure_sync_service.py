import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from features.sync.structures.service import SchoolSyncService


def _repository() -> Mock:
    repository = Mock()
    repository.save_school.return_value = SimpleNamespace(id=10)
    repository.save_program.return_value = SimpleNamespace(id=20)
    repository.save_structure.return_value = SimpleNamespace(id=30)
    repository.save_semester.return_value = SimpleNamespace(id=40)
    repository.save_semester_module.return_value = SimpleNamespace(id=50)
    repository.find_missing_school_cms_ids.return_value = []
    repository.find_missing_program_cms_ids.return_value = []
    repository.find_missing_structure_cms_ids.return_value = []
    repository.find_missing_semester_cms_ids.return_value = []
    repository.find_missing_semester_module_cms_ids.return_value = []
    return repository


class SchoolSyncServiceTests(unittest.TestCase):
    def test_import_all_schools_structures_raises_when_school_verification_fails(self):
        repository = _repository()
        repository.find_missing_school_cms_ids.return_value = [101]
        service = SchoolSyncService(repository)

        with (
            patch(
                "features.sync.structures.service.scrape_all_schools",
                return_value=[{"cms_id": 101, "code": "SCI", "name": "Science"}],
            ),
            patch(
                "features.sync.structures.service.scrape_programs",
                return_value=[],
            ),
        ):
            with self.assertRaises(RuntimeError):
                service.import_all_schools_structures(lambda *_: None)

    def test_import_all_schools_structures_raises_when_program_verification_fails(self):
        repository = _repository()
        repository.find_missing_program_cms_ids.return_value = [201]
        service = SchoolSyncService(repository)

        with (
            patch(
                "features.sync.structures.service.scrape_all_schools",
                return_value=[{"cms_id": 101, "code": "SCI", "name": "Science"}],
            ),
            patch(
                "features.sync.structures.service.scrape_programs",
                return_value=[
                    {
                        "cms_id": 201,
                        "code": "BIO",
                        "name": "Biology",
                        "level": "degree",
                    }
                ],
            ),
        ):
            with self.assertRaises(RuntimeError):
                service.import_all_schools_structures(lambda *_: None)

    def test_import_program_structures_raises_when_structure_verification_fails(self):
        repository = _repository()
        repository.find_missing_structure_cms_ids.return_value = [301]
        service = SchoolSyncService(repository)

        with patch(
            "features.sync.structures.service.scrape_structures",
            return_value=[{"cms_id": 301, "code": "2026-A", "desc": "2026-A"}],
        ):
            with self.assertRaises(RuntimeError):
                service.import_program_structures(201, lambda *_: None)

    def test_import_semesters_raises_when_semester_verification_fails(self):
        repository = _repository()
        repository.find_missing_semester_cms_ids.return_value = [401]
        service = SchoolSyncService(repository)

        with patch(
            "features.sync.structures.service.scrape_semesters",
            return_value=[
                {
                    "cms_id": 401,
                    "semester_number": "01",
                    "name": "Year 1 Sem 1",
                    "total_credits": 18.0,
                }
            ],
        ):
            with self.assertRaises(RuntimeError):
                service._import_semesters(
                    [{"cms_id": 301, "code": "2026-A", "_db_id": 30}],
                    "BIO",
                    lambda *_: None,
                )

    def test_import_semester_modules_concurrent_raises_when_verification_fails(self):
        repository = _repository()
        repository.find_missing_semester_module_cms_ids.return_value = [501]
        service = SchoolSyncService(repository)

        with patch(
            "features.sync.structures.service.scrape_semester_modules",
            return_value=[
                {
                    "cms_id": 501,
                    "module_code": "BIO101",
                    "module_name": "Biology 101",
                    "type": "Core",
                    "credits": 3.0,
                    "hidden": False,
                }
            ],
        ):
            with self.assertRaises(RuntimeError):
                service._import_semester_modules_concurrent(
                    [{"cms_id": 401, "name": "Year 1 Sem 1", "_db_id": 40}],
                    "2026-A",
                    lambda *_: None,
                )

    def test_import_semester_modules_concurrent_verifies_each_semester_batch(self):
        repository = _repository()
        service = SchoolSyncService(repository)
        progress = Mock()

        with patch(
            "features.sync.structures.service.scrape_semester_modules",
            side_effect=[
                [
                    {
                        "cms_id": 501,
                        "module_code": "BIO101",
                        "module_name": "Biology 101",
                        "type": "Core",
                        "credits": 3.0,
                        "hidden": False,
                    }
                ],
                [
                    {
                        "cms_id": 502,
                        "module_code": "CHE101",
                        "module_name": "Chemistry 101",
                        "type": "Core",
                        "credits": 3.0,
                        "hidden": False,
                    }
                ],
            ],
        ):
            service._import_semester_modules_concurrent(
                [
                    {"cms_id": 401, "name": "Year 1 Sem 1", "_db_id": 40},
                    {"cms_id": 402, "name": "Year 1 Sem 2", "_db_id": 41},
                ],
                "2026-A",
                progress,
            )

        self.assertEqual(repository.save_semester_module.call_count, 2)
        verified_batches = sorted(
            tuple(call.args[0])
            for call in repository.find_missing_semester_module_cms_ids.call_args_list
        )
        self.assertEqual(verified_batches, [(501,), (502,)])

    def test_import_all_schools_structures_imports_full_hierarchy_when_verified(self):
        repository = _repository()
        service = SchoolSyncService(repository)
        progress = Mock()

        with (
            patch(
                "features.sync.structures.service.scrape_all_schools",
                return_value=[{"cms_id": 101, "code": "SCI", "name": "Science"}],
            ),
            patch(
                "features.sync.structures.service.scrape_programs",
                return_value=[
                    {
                        "cms_id": 201,
                        "code": "BIO",
                        "name": "Biology",
                        "level": "degree",
                    }
                ],
            ),
            patch(
                "features.sync.structures.service.scrape_structures",
                return_value=[{"cms_id": 301, "code": "2026-A", "desc": "2026-A"}],
            ),
            patch(
                "features.sync.structures.service.scrape_semesters",
                return_value=[
                    {
                        "cms_id": 401,
                        "semester_number": "01",
                        "name": "Year 1 Sem 1",
                        "total_credits": 18.0,
                    }
                ],
            ),
            patch(
                "features.sync.structures.service.scrape_semester_modules",
                return_value=[
                    {
                        "cms_id": 501,
                        "module_code": "BIO101",
                        "module_name": "Biology 101",
                        "type": "Core",
                        "credits": 3.0,
                        "hidden": False,
                    }
                ],
            ),
        ):
            service.import_all_schools_structures(progress, fetch_semesters=True)

        repository.save_school.assert_called_once()
        repository.save_program.assert_called_once()
        repository.save_structure.assert_called_once()
        repository.save_semester.assert_called_once()
        repository.save_semester_module.assert_called_once()
        repository.find_missing_school_cms_ids.assert_called_once_with([101])
        repository.find_missing_program_cms_ids.assert_called_once_with([201])
        repository.find_missing_structure_cms_ids.assert_called_once_with([301])
        repository.find_missing_semester_cms_ids.assert_called_once_with([401])
        repository.find_missing_semester_module_cms_ids.assert_called_once_with([501])
        self.assertEqual(
            progress.call_args_list[-1].args,
            ("Completed import for 1 school(s)", 1, 1),
        )

    def test_import_all_schools_structures_completes_when_all_entities_verify(self):
        repository = _repository()
        service = SchoolSyncService(repository)
        progress = Mock()

        with (
            patch(
                "features.sync.structures.service.scrape_all_schools",
                return_value=[{"cms_id": 101, "code": "SCI", "name": "Science"}],
            ),
            patch(
                "features.sync.structures.service.scrape_programs",
                return_value=[
                    {
                        "cms_id": 201,
                        "code": "BIO",
                        "name": "Biology",
                        "level": "degree",
                    }
                ],
            ),
            patch.object(service, "_import_structures") as import_structures,
        ):
            service.import_all_schools_structures(progress, fetch_semesters=True)

        import_structures.assert_called_once()
        repository.find_missing_program_cms_ids.assert_called_once_with([201])
        repository.find_missing_school_cms_ids.assert_called_once_with([101])
        self.assertEqual(
            progress.call_args_list[-1].args,
            ("Completed import for 1 school(s)", 1, 1),
        )


if __name__ == "__main__":
    unittest.main()
