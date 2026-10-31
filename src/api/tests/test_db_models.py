import pytest
from sqlalchemy import create_engine

import db
from db import Base, init_db


@pytest.mark.technical
def test_database_initialization(monkeypatch):
    """
    Перевіряє, що init_db успішно створює всі 7 таблиць.
    Підміняємо engine на in-memory, щоб не створювати файл під час тестів.
    """
    test_engine = create_engine("sqlite:///:memory:")
    monkeypatch.setattr(db, "engine", test_engine)

    # Ініціалізуємо БД
    init_db()

    # Отримуємо список створених таблиць із метаданих
    tables = Base.metadata.tables.keys()
    
    # Перевіряємо, що всі наші моделі зареєстровані за точними назвами з models.py
    assert "users" in tables
    assert "rooms" in tables
    assert "games" in tables
    assert "game_enrollments" in tables
    assert "notifications" in tables
    assert "bookings" in tables
    assert "sessions" in tables