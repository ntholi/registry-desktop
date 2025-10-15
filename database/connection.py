import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

TIMEOUT_SECONDS = 120


def get_engine(use_local: bool = False) -> Engine:
    print("Using local database" if use_local else "Using production database")
    if use_local:
        engine = create_engine(
            "sqlite:///../registry-web/local.db",
            connect_args={"check_same_thread": False, "timeout": TIMEOUT_SECONDS},
            echo=False,
            pool_pre_ping=True,
            poolclass=NullPool,
        )
        return engine
    else:
        if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
            url = f"{TURSO_DATABASE_URL}?authToken={TURSO_AUTH_TOKEN}"
            engine = create_engine(
                f"sqlite+{url}",
                connect_args={"check_same_thread": False, "timeout": TIMEOUT_SECONDS},
                echo=False,
                pool_pre_ping=True,
                poolclass=NullPool,
            )
            return engine
        else:
            raise ValueError("TURSO_AUTH_TOKEN or TURSO_DATABASE_URL missing")
