import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.pool import NullPool

load_dotenv()

DATABASE_ENV = os.getenv("DATABASE_ENV", "local")
DESKTOP_ENV = os.getenv("DESKTOP_ENV", "prod")
DATABASE_LOCAL_URL = os.getenv("DATABASE_LOCAL_URL")
DATABASE_REMOTE_URL = os.getenv("DATABASE_REMOTE_URL")

TIMEOUT_SECONDS = 120


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
