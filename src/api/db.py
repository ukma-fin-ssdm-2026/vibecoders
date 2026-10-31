import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Адреса БД береться зі змінних середовища або використовується локальна SQLite за замовчуванням
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///club.db")

# Налаштування engine для SQLite (check_same_thread потрібен для FastAPI)
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """Створює всі таблиці в базі даних."""
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
