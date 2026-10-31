import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import db
from db import Base, create_database_engine, enable_sqlite_foreign_keys, init_db, resolve_database_url
from models import Token


@pytest.mark.technical
def test_database_initialization(monkeypatch):
    """
    Перевіряє, що init_db успішно створює всі 7 таблиць.
    Підміняємо engine на in-memory, щоб не створювати файл під час тестів.
    """
    test_engine = create_engine("sqlite:///:memory:")
    enable_sqlite_foreign_keys(test_engine)
    monkeypatch.setattr(db, "engine", test_engine)

    # Ініціалізуємо БД
    init_db()

    # Отримуємо список створених таблиць із метаданих
    tables = Base.metadata.tables.keys()

    # Перевіряємо, що всі наші моделі зареєстровані
    assert "users" in tables
    assert "rooms" in tables
    assert "games" in tables
    assert "enrollments" in tables
    assert "notifications" in tables
    assert "room_blocks" in tables
    assert "tokens" in tables


@pytest.mark.technical
def test_default_database_url_uses_configured_absolute_data_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    url = resolve_database_url()

    assert Path(url.database).is_absolute()
    assert Path(url.database) == tmp_path / "club.db"


@pytest.mark.technical
def test_sqlite_foreign_keys_are_enforced(tmp_path):
    test_engine = create_database_engine(f"sqlite:///{tmp_path / 'foreign-keys.db'}")
    Base.metadata.create_all(bind=test_engine)
    session = sessionmaker(bind=test_engine)()
    try:
        with pytest.raises(IntegrityError):
            session.add(Token(id="orphan-token", user_id="missing-user"))
            session.commit()
        session.rollback()
    finally:
        session.close()
        test_engine.dispose()
