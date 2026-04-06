from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL, make_url

from base.runtime_config import CountryConfig, get_available_countries, get_country_config
from database.connection import (
    configure_database_urls_for_country,
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


def parse_country_selection(
    selection: str, countries: list[CountryConfig] | None = None
) -> CountryConfig | None:
    available_countries = countries or get_available_countries()
    normalized = selection.strip().lower()

    if not normalized:
        return None

    for index, config in enumerate(available_countries, start=1):
        if normalized in {str(index), config.code, config.label.lower()}:
            return config

    return None


def prompt_for_country_selection(
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> CountryConfig:
    countries = get_available_countries()
    output_func("Select the database to create or initialize:")

    for index, config in enumerate(countries, start=1):
        output_func(f"{index}. {config.label} ({config.database_name})")

    accepted_values = " / ".join(
        f"{index}:{config.code}" for index, config in enumerate(countries, start=1)
    )

    while True:
        selected_country = parse_country_selection(
            input_func("Choose a database: "), countries
        )

        if selected_country:
            return selected_country

        output_func(f"Invalid selection. Enter one of {accepted_values}.")


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


def bootstrap_database(
    admin_database: str = "postgres", country_code: str | None = None
) -> BootstrapResult:
    if country_code:
        configure_database_urls_for_country(country_code)

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
    parser.add_argument(
        "--country",
        choices=[config.code for config in get_available_countries()],
        help="use a specific country/database without prompting",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    try:
        selected_country = (
            get_country_config(args.country)
            if args.country
            else prompt_for_country_selection()
        )
        result = bootstrap_database(
            admin_database=args.admin_db,
            country_code=selected_country.code,
        )
    except Exception as exc:
        print(f"Database bootstrap failed: {exc}")
        raise SystemExit(1) from exc

    action = "Created" if result.database_created else "Using existing"

    print(f"Country: {selected_country.label}")
    print(f"Environment: {result.environment}")
    print(f"Database: {result.database_name}")
    print(f"Status: {action} database and ensured all tables exist")


if __name__ == "__main__":
    main()
