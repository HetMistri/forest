from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()


def _normalized_database_url() -> str | None:
    if not settings.database_url:
        return None
    if settings.database_url.startswith("postgresql://"):
        return settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return settings.database_url


@lru_cache
def get_engine() -> Engine | None:
    database_url = _normalized_database_url()
    if not database_url:
        return None
    return create_engine(database_url, pool_pre_ping=True)


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
