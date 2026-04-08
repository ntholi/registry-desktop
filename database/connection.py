import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.pool import NullPool

from base.runtime_config import (
    get_app_settings,
    get_current_country_code,
    get_current_database_name,
    set_current_country,
)

DATABASE_ENV: str = "local"
DESKTOP_ENV: str = os.getenv("DESKTOP_ENV", "prod")
DATABASE_LOCAL_URL: str | None = None
DATABASE_REMOTE_URL: str | None = None

TIMEOUT_SECONDS = 120


def _is_remote_host(host: str) -> bool:
    normalized = host.strip().lower()
    return normalized not in {"localhost", "127.0.0.1", "::1"}


def _build_database_url() -> str | None:
    if not get_current_country_code():
        return None

    settings = get_app_settings()
    if not settings.database_host or not settings.database_user:
        return None

    database_url = URL.create(
        "postgresql",
        username=settings.database_user,
        password=settings.database_password or None,
        host=settings.database_host,
        port=settings.database_port,
        database=get_current_database_name(),
    )

    return database_url.render_as_string(hide_password=False)


def configure_database_urls_for_country(country_code: str | None = None) -> None:
    global DATABASE_ENV, DATABASE_LOCAL_URL, DATABASE_REMOTE_URL

    if country_code:
        set_current_country(country_code)

    database_url = _build_database_url()
    if not database_url:
        DATABASE_ENV = "local"
        DATABASE_LOCAL_URL = None
        DATABASE_REMOTE_URL = None
        return

    if _is_remote_host(get_app_settings().database_host):
        DATABASE_ENV = "remote"
        DATABASE_REMOTE_URL = database_url
        DATABASE_LOCAL_URL = None
        return

    DATABASE_ENV = "local"
    DATABASE_LOCAL_URL = database_url
    DATABASE_REMOTE_URL = None


def is_remote_database() -> bool:
    if DATABASE_REMOTE_URL and not DATABASE_LOCAL_URL:
        return True
    if DATABASE_LOCAL_URL and not DATABASE_REMOTE_URL:
        return False

    return DATABASE_ENV.strip().lower() == "remote"


def get_database_env_label() -> str:
    return "remote" if is_remote_database() else "local"


def get_database_url() -> str:
    if not DATABASE_LOCAL_URL and not DATABASE_REMOTE_URL:
        configure_database_urls_for_country()

    if is_remote_database():
        if not DATABASE_REMOTE_URL:
            raise ValueError(
                "Database connection is not configured. Save a country, host, port, and user before continuing."
            )
        return DATABASE_REMOTE_URL

    if not DATABASE_LOCAL_URL:
        raise ValueError(
            "Database connection is not configured. Save a country, host, port, and user before continuing."
        )
    return DATABASE_LOCAL_URL


def create_database_engine(database_url: str | URL) -> Engine:
    return create_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        poolclass=NullPool,
    )


def get_engine() -> Engine:
    database_url = get_database_url()

    if is_remote_database():
        print("Using remote PostgreSQL database")
    else:
        print("Using local PostgreSQL database")

    return create_database_engine(database_url)


configure_database_urls_for_country()
