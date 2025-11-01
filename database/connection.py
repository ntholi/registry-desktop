import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

load_dotenv()

DATABASE_ENV = os.getenv("DATABASE_ENV", "local")
DATABASE_LOCAL_URL = os.getenv("DATABASE_LOCAL_URL")
DATABASE_REMOTE_URL = os.getenv("DATABASE_REMOTE_URL")

TIMEOUT_SECONDS = 120


def get_engine() -> Engine:
    db_env = DATABASE_ENV.lower()

    if db_env == "local":
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
    elif db_env == "remote":
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
        raise ValueError(
            f"Invalid DATABASE_ENV value: {db_env}. Must be 'local' or 'remote'"
        )
