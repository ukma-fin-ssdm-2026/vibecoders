import os
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import declarative_base, sessionmaker


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


def init_db():
    """Створює всі таблиці в базі даних."""
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
