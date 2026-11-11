"""Підключення до бази даних (SQLAlchemy 2, за замовчуванням SQLite).

Адреса береться зі змінної DATABASE_URL. Відносний шлях SQLite (наприклад, ``sqlite:///club.db``)
розв'язується відносно каталогу даних DATA_DIR (за замовчуванням ``<корінь репозиторію>/data``),
тому файл БД не залежить від того, з якої папки запущено сервер.
"""

import logging
import math
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url, URL
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger("api.db")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = "sqlite:///club.db"


def resolve_database_url(database_url: Optional[str] = None) -> URL:
    configured_url = database_url or os.getenv("DATABASE_URL")
    if configured_url is None:
        data_dir = Path(os.getenv("DATA_DIR", PROJECT_ROOT)).expanduser().resolve()
        configured_url = f"sqlite:///{data_dir / 'club.db'}"

    url = make_url(configured_url)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        if not url.database.startswith("file:"):
            database_path = Path(url.database).expanduser().resolve()
            database_path.parent.mkdir(parents=True, exist_ok=True)
            url = url.set(database=str(database_path))
    return url


def enable_sqlite_foreign_keys(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def set_sqlite_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def configure_engine(target: Engine) -> Engine:
    """Вмикає перевірку зовнішніх ключів для SQLite. Викликається і для тестового engine."""
    enable_sqlite_foreign_keys(target)
    return target


DEFAULT_DB_TIMEOUT_SECONDS = 10.0


def read_db_timeout(raw_value: Optional[str] = None) -> float:
    raw = os.getenv("DB_TIMEOUT_SECONDS") if raw_value is None else raw_value
    if raw is None or not raw.strip():
        return DEFAULT_DB_TIMEOUT_SECONDS
    try:
        timeout = float(raw)
    except ValueError:
        logger.warning("DB_TIMEOUT_SECONDS=%r is not a number, using %s", raw, DEFAULT_DB_TIMEOUT_SECONDS)
        return DEFAULT_DB_TIMEOUT_SECONDS
    if not math.isfinite(timeout) or timeout <= 0:
        logger.warning("DB_TIMEOUT_SECONDS=%r is out of range, using %s", raw, DEFAULT_DB_TIMEOUT_SECONDS)
        return DEFAULT_DB_TIMEOUT_SECONDS
    return timeout


def create_database_engine(database_url: Optional[str] = None) -> Engine:
    url = resolve_database_url(database_url)
    connect_args = (
        {"check_same_thread": False, "timeout": read_db_timeout()} if url.get_backend_name() == "sqlite" else {}
    )
    engine = create_engine(url, connect_args=connect_args)
    enable_sqlite_foreign_keys(engine)
    return engine


DATABASE_URL = resolve_database_url()
engine = create_database_engine(str(DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Сесія з commit/rollback. SessionLocal береться під час виклику, тож тести можуть її підмінити."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Створює каталог для файлу SQLite (якщо його немає) і всі таблиці."""
    import models  # noqa: F401

    database = engine.url.database
    if engine.dialect.name == "sqlite" and database and database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
