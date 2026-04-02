from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine.url import make_url

from database.connection import get_database_env_label, get_database_url


@dataclass(slots=True)
class BackupResult:
    environment: str
    database_name: str
    output_path: Path


def get_default_output_path(database_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return Path("backup_db") / f"{database_name}-{timestamp}.dump"


def get_pg_dump_path() -> str:
    pg_dump_path = shutil.which("pg_dump")
    if not pg_dump_path:
        raise FileNotFoundError("pg_dump was not found in PATH")
    return pg_dump_path


def get_pg_dump_url() -> tuple[str, str | None]:
    database_url = make_url(get_database_url())
    database_name = database_url.database

    if not database_name:
        raise ValueError("Database URL must include a database name")

    drivername = database_url.drivername.split("+", 1)[0]
    dump_url = database_url.set(drivername=drivername, password=None)
    return dump_url.render_as_string(hide_password=False), database_url.password


def create_database_dump(output_path: str | None = None) -> BackupResult:
    database_url = make_url(get_database_url())
    database_name = database_url.database

    if not database_name:
        raise ValueError("Database URL must include a database name")

    target_path = (
        Path(output_path).expanduser()
        if output_path
        else get_default_output_path(database_name)
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)

    dump_url, password = get_pg_dump_url()
    env = os.environ.copy()

    if password:
        env["PGPASSWORD"] = password

    subprocess.run(
        [
            get_pg_dump_path(),
            "--format=custom",
            "--file",
            str(target_path),
            "--dbname",
            dump_url,
        ],
        check=True,
        env=env,
    )

    return BackupResult(
        environment=get_database_env_label(),
        database_name=database_name,
        output_path=target_path.resolve(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    try:
        result = create_database_dump(output_path=args.output)
    except Exception as exc:
        print(f"Database backup failed: {exc}")
        raise SystemExit(1) from exc

    print(f"Environment: {result.environment}")
    print(f"Database: {result.database_name}")
    print(f"Backup: {result.output_path}")


if __name__ == "__main__":
    main()
