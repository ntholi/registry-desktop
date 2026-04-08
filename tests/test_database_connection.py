import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from base import runtime_config
from database import connection as db_connection


class DatabaseConnectionTests(unittest.TestCase):
    def setUp(self):
        self.original_settings = runtime_config._settings
        self.original_country_code = runtime_config._current_country_code
        self.original_database_env = db_connection.DATABASE_ENV
        self.original_desktop_env = db_connection.DESKTOP_ENV
        self.original_local_url = db_connection.DATABASE_LOCAL_URL
        self.original_remote_url = db_connection.DATABASE_REMOTE_URL

    def tearDown(self):
        runtime_config._settings = self.original_settings
        runtime_config._current_country_code = self.original_country_code
        db_connection.DATABASE_ENV = self.original_database_env
        db_connection.DESKTOP_ENV = self.original_desktop_env
        db_connection.DATABASE_LOCAL_URL = self.original_local_url
        db_connection.DATABASE_REMOTE_URL = self.original_remote_url

    def test_configure_database_urls_for_local_host_uses_local_database_url(self):
        runtime_config._settings = runtime_config.AppSettings(
            country_code="botswana",
            database_host="localhost",
            database_port=5432,
            database_user="dev",
            database_password="111111",
        )
        runtime_config._current_country_code = "botswana"

        db_connection.configure_database_urls_for_country("botswana")

        self.assertEqual(db_connection.get_database_env_label(), "local")
        self.assertEqual(
            db_connection.DATABASE_LOCAL_URL,
            "postgresql://dev:111111@localhost:5432/cms_botswana",
        )
        self.assertIsNone(db_connection.DATABASE_REMOTE_URL)

    def test_configure_database_urls_for_remote_host_uses_remote_database_url(self):
        runtime_config._settings = runtime_config.AppSettings(
            country_code="eswatini",
            database_host="db.example.com",
            database_port=6543,
            database_user="registry",
            database_password="secret",
        )
        runtime_config._current_country_code = "eswatini"

        db_connection.configure_database_urls_for_country("eswatini")

        self.assertEqual(db_connection.get_database_env_label(), "remote")
        self.assertEqual(
            db_connection.DATABASE_REMOTE_URL,
            "postgresql://registry:secret@db.example.com:6543/cms_eswatini",
        )
        self.assertIsNone(db_connection.DATABASE_LOCAL_URL)

    def test_save_runtime_settings_persists_selected_country_and_connection_fields(
        self,
    ):
        with TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"
            with patch(
                "base.runtime_config.get_settings_file_path",
                return_value=settings_path,
            ):
                saved_settings = runtime_config.save_runtime_settings(
                    country_code="botswana",
                    database_host="db.internal",
                    database_port="6000",
                    database_user="registry",
                    database_password="secret",
                )
                loaded_settings = runtime_config._load_settings()
                payload = json.loads(settings_path.read_text(encoding="utf-8"))

                self.assertTrue(settings_path.exists())
                self.assertEqual(payload["country_code"], "botswana")
                self.assertEqual(payload["database_host"], "db.internal")
                self.assertEqual(payload["database_port"], 6000)
                self.assertEqual(payload["database_user"], "registry")
                self.assertEqual(payload["database_password"], "secret")

        self.assertEqual(saved_settings.country_code, "botswana")
        self.assertEqual(loaded_settings.country_code, "botswana")
        self.assertEqual(loaded_settings.database_host, "db.internal")
        self.assertEqual(loaded_settings.database_port, 6000)
        self.assertEqual(loaded_settings.database_user, "registry")
        self.assertEqual(loaded_settings.database_password, "secret")
