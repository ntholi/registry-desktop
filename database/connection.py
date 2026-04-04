import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import NullPool

from base.runtime_config import (
    get_current_country_code,
    get_current_database_name,
    set_current_country,
)

load_dotenv()

DATABASE_ENV: str = os.getenv("DATABASE_ENV", "local")
DESKTOP_ENV: str = os.getenv("DESKTOP_ENV", "prod")
DATABASE_LOCAL_URL: str | None = os.getenv("DATABASE_LOCAL_URL")
DATABASE_REMOTE_URL: str | None = os.getenv("DATABASE_REMOTE_URL")
_DATABASE_LOCAL_URL_TEMPLATE: str | None = DATABASE_LOCAL_URL
_DATABASE_REMOTE_URL_TEMPLATE: str | None = DATABASE_REMOTE_URL

TIMEOUT_SECONDS = 120


def _get_country_specific_database_url(base_name: str) -> str | None:
    country_code = get_current_country_code().upper()
    return os.getenv(f"{base_name}_{country_code}")


def _replace_database_name(database_url: str | None) -> str | None:
    if not database_url:
        return None

    database_name = get_current_database_name()
    url = make_url(database_url)

    if not url.database:
        raise ValueError("Database URL must include a database name")

    return url.set(database=database_name).render_as_string(hide_password=False)


def configure_database_urls_for_country(country_code: str | None = None) -> None:
    global DATABASE_LOCAL_URL, DATABASE_REMOTE_URL

    if country_code:
        set_current_country(country_code)

    DATABASE_LOCAL_URL = _get_country_specific_database_url(
        "DATABASE_LOCAL_URL"
    ) or _replace_database_name(_DATABASE_LOCAL_URL_TEMPLATE)
    DATABASE_REMOTE_URL = _get_country_specific_database_url(
        "DATABASE_REMOTE_URL"
    ) or _replace_database_name(_DATABASE_REMOTE_URL_TEMPLATE)


def is_remote_database() -> bool:
    db_env = DATABASE_ENV.strip().lower()
    desktop_env = DESKTOP_ENV.strip().lower()
    return db_env == "remote" or desktop_env == "prod"


def get_database_env_label() -> str:
    return "remote" if is_remote_database() else "local"


def get_database_url() -> str:
    if is_remote_database():
        if not DATABASE_REMOTE_URL:
            raise ValueError("DATABASE_REMOTE_URL environment variable is missing")
        return DATABASE_REMOTE_URL

    if not DATABASE_LOCAL_URL:
        raise ValueError("DATABASE_LOCAL_URL environment variable is missing")
    return DATABASE_LOCAL_URL


def create_database_engine(database_url: str | URL) -> Engine:
    return create_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        poolclass=NullPool,
    )


def get_engine() -> Engine:
    use_remote = is_remote_database()
    database_url = get_database_url()

    if use_remote:
        print("Using remote PostgreSQL database")
    else:
        print("Using local PostgreSQL database")

    return create_database_engine(database_url)


configure_database_urls_for_country()
