from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine.url import make_url

from database.connection import get_database_env_label, get_database_url

CUSTOM_BACKUP_SUFFIXES = {".dump", ".backup"}
SUPPORTED_BACKUP_SUFFIXES = CUSTOM_BACKUP_SUFFIXES | {".sql"}


@dataclass(slots=True)
class RestoreResult:
    environment: str
    database_name: str
    input_path: Path


def get_default_backup_dir() -> Path:
    return Path("backup_db")


def list_backups(backup_dir: str | Path | None = None) -> list[Path]:
    target_dir = (
        Path(backup_dir).expanduser()
        if backup_dir is not None
        else get_default_backup_dir()
    )

    if not target_dir.exists():
        return []

    backups = [
        path
        for path in target_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_BACKUP_SUFFIXES
    ]
    return sorted(
        backups,
        key=lambda path: (path.stat().st_mtime, path.name.lower()),
        reverse=True,
    )


def get_latest_backup_path(backup_dir: str | Path | None = None) -> Path:
    backups = list_backups(backup_dir)

    if not backups:
        raise FileNotFoundError("No backup files were found in backup_db")

    custom_backups = [
        path for path in backups if path.suffix.lower() in CUSTOM_BACKUP_SUFFIXES
    ]

    selected = custom_backups[0] if custom_backups else backups[0]
    return selected.resolve()


def resolve_input_path(
    input_path: str | Path | None = None,
    backup_dir: str | Path | None = None,
) -> Path:
    if input_path is None:
        return get_latest_backup_path(backup_dir)

    selected = Path(input_path).expanduser()
    if not selected.exists() or not selected.is_file():
        raise FileNotFoundError(f"Backup file was not found: {selected}")
    if selected.suffix.lower() not in SUPPORTED_BACKUP_SUFFIXES:
        raise ValueError(
            "Backup file must use one of these extensions: .dump, .backup, .sql"
        )
    return selected.resolve()


def get_pg_restore_path() -> str:
    pg_restore_path = shutil.which("pg_restore")
    if not pg_restore_path:
        raise FileNotFoundError("pg_restore was not found in PATH")
    return pg_restore_path


def get_psql_path() -> str:
    psql_path = shutil.which("psql")
    if not psql_path:
        raise FileNotFoundError("psql was not found in PATH")
    return psql_path


def get_restore_url() -> tuple[str, str | None, str]:
    database_url = make_url(get_database_url())
    database_name = database_url.database

    if not database_name:
        raise ValueError("Database URL must include a database name")

    drivername = database_url.drivername.split("+", 1)[0]
    restore_url = database_url.set(drivername=drivername, password=None)
    return (
        restore_url.render_as_string(hide_password=False),
        database_url.password,
        database_name,
    )


def build_restore_command(input_path: Path, restore_url: str) -> list[str]:
    if input_path.suffix.lower() in CUSTOM_BACKUP_SUFFIXES:
        return [
            get_pg_restore_path(),
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            restore_url,
            str(input_path),
        ]

    if input_path.suffix.lower() == ".sql":
        return [
            get_psql_path(),
            "--set",
            "ON_ERROR_STOP=1",
            "--dbname",
            restore_url,
            "--file",
            str(input_path),
        ]

    raise ValueError(
        "Backup file must use one of these extensions: .dump, .backup, .sql"
    )


def confirm_restore(
    input_path: Path,
    environment: str,
    database_name: str,
    input_func=input,
    output_func=print,
) -> bool:
    output_func(f"Environment: {environment}")
    output_func(f"Database: {database_name}")
    output_func(f"Backup: {input_path}")
    confirmation = input_func("Type YES to continue restoring this backup: ").strip()
    return confirmation == "YES"


def restore_database(
    input_path: str | Path | None = None,
    backup_dir: str | Path | None = None,
) -> RestoreResult:
    selected_input = resolve_input_path(input_path=input_path, backup_dir=backup_dir)
    restore_url, password, database_name = get_restore_url()
    env = os.environ.copy()

    if password:
        env["PGPASSWORD"] = password

    subprocess.run(
        build_restore_command(selected_input, restore_url),
        check=True,
        env=env,
    )

    return RestoreResult(
        environment=get_database_env_label(),
        database_name=database_name,
        input_path=selected_input,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--backup-dir")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--print-input", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    try:
        selected_input = resolve_input_path(
            input_path=args.input,
            backup_dir=args.backup_dir,
        )
        if args.print_input:
            print(selected_input)
            return

        restore_url, _, database_name = get_restore_url()
        del restore_url

        if not args.yes and not confirm_restore(
            selected_input,
            get_database_env_label(),
            database_name,
        ):
            print("Database restore cancelled")
            raise SystemExit(1)

        result = restore_database(
            input_path=selected_input,
            backup_dir=args.backup_dir,
        )
    except Exception as exc:
        print(f"Database restore failed: {exc}")
        raise SystemExit(1) from exc

    print(f"Environment: {result.environment}")
    print(f"Database: {result.database_name}")
    print(f"Restored from: {result.input_path}")


if __name__ == "__main__":
    main()
