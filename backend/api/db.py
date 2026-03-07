from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()


def _normalized_database_url() -> str | None:
    if not settings.database_url:
        return None
    database_url = settings.database_url.strip()
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def _resolve_sslmode(database_url: str) -> str:
    env_sslmode = (os.getenv("DATABASE_SSLMODE") or os.getenv("PGSSLMODE") or "").strip()
    if env_sslmode:
        return env_sslmode

    try:
        host = (make_url(database_url).host or "").strip().lower()
    except Exception:
        host = ""

    local_hosts = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "db",
        "forest-postgis",
        "postgres",
    }
    return "disable" if host in local_hosts else "require"


@lru_cache
def get_engine() -> Engine | None:
    database_url = _normalized_database_url()
    if not database_url:
        return None
    sslmode = _resolve_sslmode(database_url)
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_use_lifo=True,
        connect_args={
            "sslmode": sslmode,
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    )


def get_session_local() -> sessionmaker[Session] | None:
    engine = get_engine()
    if engine is None:
        return None
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    session_local = get_session_local()
    if session_local is None:
        raise RuntimeError("DATABASE_URL is not configured")

    session = session_local()
    try:
        yield session
    finally:
        session.close()


def check_db_connection() -> bool:
    engine = get_engine()
    if engine is None:
        return False

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
