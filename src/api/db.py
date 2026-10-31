"""Підключення до бази даних (SQLAlchemy 2, за замовчуванням SQLite).

Адреса береться зі змінної DATABASE_URL. Відносний шлях SQLite (наприклад, ``sqlite:///club.db``)
розв'язується відносно каталогу даних DATA_DIR (за замовчуванням ``<корінь репозиторію>/data``),
тому файл БД не залежить від того, з якої папки запущено сервер.
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR") or PROJECT_ROOT / "data").expanduser().resolve()
DEFAULT_DATABASE_URL = "sqlite:///club.db"


def resolve_database_url(raw_url: Optional[str] = None) -> str:
    """Повертає адресу БД, у якій файл SQLite має абсолютний шлях."""
    url = make_url(raw_url or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL)
    database = url.database
    if url.get_backend_name() == "sqlite" and database and database != ":memory:" and not database.startswith("file:"):
        path = Path(database).expanduser()
        if not path.is_absolute():
            path = DATA_DIR / path
        url = url.set(database=str(path))
    return url.render_as_string(hide_password=False)


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """SQLite не перевіряє зовнішні ключі, доки це не ввімкнено на кожному з'єднанні."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def configure_engine(target: Engine) -> Engine:
    """Вмикає перевірку зовнішніх ключів для SQLite. Викликається і для тестового engine."""
    if target.dialect.name == "sqlite":
        event.listen(target, "connect", _enable_sqlite_foreign_keys)
    return target


DATABASE_URL = resolve_database_url()
_is_sqlite = DATABASE_URL.startswith("sqlite")

# check_same_thread потрібен для FastAPI, timeout - щоб паралельні записи чекали, а не падали одразу.
engine = configure_engine(
    create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30} if _is_sqlite else {})
)

def resolve_database_url(database_url: Optional[str] = None) -> URL:
    configured_url = database_url or os.getenv("DATABASE_URL")
    if configured_url is None:
        data_dir = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[2])).expanduser().resolve()
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


def create_database_engine(database_url: Optional[str] = None) -> Engine:
    url = resolve_database_url(database_url)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if url.get_backend_name() == "sqlite" else {},
    )
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
