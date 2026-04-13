import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import ANY, patch

from database.restore import (
    get_latest_backup_path,
    resolve_input_path,
    restore_database,
)


class DatabaseRestoreTests(unittest.TestCase):
    def test_get_latest_backup_path_prefers_newest_custom_backup(self):
        with TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            sql_backup = backup_dir / "cms_lesotho-2026-04-12_13-32-36.sql"
            older_dump = backup_dir / "cms_lesotho-2026-04-13_13-32-36.dump"
            newer_dump = backup_dir / "cms_lesotho-2026-04-13_14-32-36.dump"

            sql_backup.write_text("select 1;", encoding="utf-8")
            older_dump.write_text("dump", encoding="utf-8")
            newer_dump.write_text("dump", encoding="utf-8")

            os.utime(sql_backup, (100, 100))
            os.utime(older_dump, (200, 200))
            os.utime(newer_dump, (300, 300))

            selected = get_latest_backup_path(backup_dir)

        self.assertEqual(selected, newer_dump.resolve())

    def test_get_latest_backup_path_falls_back_to_sql_when_no_custom_dump_exists(self):
        with TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            older_sql = backup_dir / "cms_lesotho-2026-04-12_13-32-36.sql"
            newer_sql = backup_dir / "cms_lesotho-2026-04-13_13-32-36.sql"

            older_sql.write_text("select 1;", encoding="utf-8")
            newer_sql.write_text("select 2;", encoding="utf-8")

            os.utime(older_sql, (100, 100))
            os.utime(newer_sql, (200, 200))

            selected = get_latest_backup_path(backup_dir)

        self.assertEqual(selected, newer_sql.resolve())

    def test_resolve_input_path_rejects_unsupported_extensions(self):
        with TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "cms_lesotho.txt"
            backup_path.write_text("invalid", encoding="utf-8")

            with self.assertRaises(ValueError):
                resolve_input_path(backup_path)

    def test_restore_database_uses_pg_restore_for_custom_dump(self):
        with TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "cms_lesotho.dump"
            backup_path.write_text("dump", encoding="utf-8")

            with (
                patch(
                    "database.restore.get_restore_url",
                    return_value=(
                        "postgresql://dev@localhost:5432/cms_lesotho",
                        "secret",
                        "cms_lesotho",
                    ),
                ),
                patch("database.restore.get_database_env_label", return_value="local"),
                patch(
                    "database.restore.get_pg_restore_path", return_value="pg_restore"
                ),
                patch("database.restore.subprocess.run") as run,
            ):
                result = restore_database(input_path=backup_path)

        self.assertEqual(result.database_name, "cms_lesotho")
        self.assertEqual(result.input_path, backup_path.resolve())
        run.assert_called_once_with(
            [
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "--dbname",
                "postgresql://dev@localhost:5432/cms_lesotho",
                str(backup_path.resolve()),
            ],
            check=True,
            env=ANY,
        )
        self.assertEqual(run.call_args.kwargs["env"]["PGPASSWORD"], "secret")

    def test_restore_database_uses_psql_for_sql_backup(self):
        with TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "cms_lesotho.sql"
            backup_path.write_text("select 1;", encoding="utf-8")

            with (
                patch(
                    "database.restore.get_restore_url",
                    return_value=(
                        "postgresql://dev@localhost:5432/cms_lesotho",
                        None,
                        "cms_lesotho",
                    ),
                ),
                patch("database.restore.get_database_env_label", return_value="local"),
                patch("database.restore.get_psql_path", return_value="psql"),
                patch("database.restore.subprocess.run") as run,
            ):
                restore_database(input_path=backup_path)

        run.assert_called_once_with(
            [
                "psql",
                "--set",
                "ON_ERROR_STOP=1",
                "--dbname",
                "postgresql://dev@localhost:5432/cms_lesotho",
                "--file",
                str(backup_path.resolve()),
            ],
            check=True,
            env=ANY,
        )
        self.assertNotIn("PGPASSWORD", run.call_args.kwargs["env"])

    def test_restore_database_raises_when_restore_command_fails(self):
        with TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "cms_lesotho.dump"
            backup_path.write_text("dump", encoding="utf-8")

            with (
                patch(
                    "database.restore.get_restore_url",
                    return_value=(
                        "postgresql://dev@localhost:5432/cms_lesotho",
                        "secret",
                        "cms_lesotho",
                    ),
                ),
                patch(
                    "database.restore.get_pg_restore_path", return_value="pg_restore"
                ),
                patch(
                    "database.restore.subprocess.run",
                    side_effect=subprocess.CalledProcessError(1, ["pg_restore"]),
                ),
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    restore_database(input_path=backup_path)
