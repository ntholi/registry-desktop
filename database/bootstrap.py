from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL, make_url

from database.connection import (
    create_database_engine,
    get_database_env_label,
    get_database_url,
)
from database.models import Base


@dataclass(slots=True)
class BootstrapResult:
    environment: str
    database_name: str
    database_created: bool


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def ensure_database_exists(target_url: URL, admin_database: str = "postgres") -> bool:
    database_name = target_url.database
    if not database_name:
        raise ValueError("Database URL must include a database name")

    admin_url = target_url.set(database=admin_database)
    engine = create_database_engine(admin_url)

    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": database_name},
            ).scalar()

            if exists:
                return False

            conn.execute(text(f"CREATE DATABASE {quote_identifier(database_name)}"))
            return True
    finally:
        engine.dispose()


def ensure_database_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_type WHERE typname = 'program_level'
                    ) THEN
                        CREATE TYPE program_level AS ENUM (
                            'certificate', 'diploma', 'degree', 'short_course'
                        );
                    END IF;
                END
                $$;
                """
            )
        )
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_type WHERE typname = 'next_of_kin_relationship'
                    ) THEN
                        CREATE TYPE next_of_kin_relationship AS ENUM (
                            'Parent', 'Brother', 'Sister', 'Spouse', 'Child', 'Relative',
                            'Friend', 'Guardian', 'Other', 'Mother', 'Father', 'Husband',
                            'Wife', 'Permanent', 'Self'
                        );
                    END IF;
                END
                $$;
                """
            )
        )

    Base.metadata.create_all(engine)


def bootstrap_database(admin_database: str = "postgres") -> BootstrapResult:
    database_url = get_database_url()
    target_url = make_url(database_url)
    database_name = target_url.database

    if not database_name:
        raise ValueError("Database URL must include a database name")

    database_created = ensure_database_exists(target_url, admin_database)
    engine = create_database_engine(target_url)

    try:
        ensure_database_schema(engine)
    finally:
        engine.dispose()

    return BootstrapResult(
        environment=get_database_env_label(),
        database_name=database_name,
        database_created=database_created,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-db", default="postgres")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    try:
        result = bootstrap_database(admin_database=args.admin_db)
    except Exception as exc:
        print(f"Database bootstrap failed: {exc}")
        raise SystemExit(1) from exc

    action = "Created" if result.database_created else "Using existing"

    print(f"Environment: {result.environment}")
    print(f"Database: {result.database_name}")
    print(f"Status: {action} database and ensured all tables exist")


if __name__ == "__main__":
    main()
