import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
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


def get_engine() -> Engine:
    use_remote = is_remote_database()

    if use_remote:
        if not DATABASE_REMOTE_URL:
            raise ValueError("DATABASE_REMOTE_URL environment variable is missing")

        print("Using remote PostgreSQL database")
        engine = create_engine(
            DATABASE_REMOTE_URL,
            echo=False,
            pool_pre_ping=True,
            poolclass=NullPool,
        )
        return engine
    else:
        if not DATABASE_LOCAL_URL:
            raise ValueError("DATABASE_LOCAL_URL environment variable is missing")

        print("Using local PostgreSQL database")
        engine = create_engine(
            DATABASE_LOCAL_URL,
            echo=False,
            pool_pre_ping=True,
            poolclass=NullPool,
        )
        return engine
