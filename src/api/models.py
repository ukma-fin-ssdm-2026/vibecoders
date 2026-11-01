from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    contacts: Mapped[str] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str] = mapped_column(String, nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    sessions = relationship("Token", back_populates="user", cascade="all, delete-orphan")
    games = relationship("Game", back_populates="master", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", back_populates="player", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    user = relationship("User", back_populates="sessions")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    games = relationship("Game", back_populates="room", cascade="all, delete-orphan")
    blocks = relationship("RoomBlock", back_populates="room", cascade="all, delete-orphan")


class RoomBlock(Base):
    __tablename__ = "room_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(String, ForeignKey("rooms.id"), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    room = relationship("Room", back_populates="blocks")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    master_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    room_id: Mapped[str] = mapped_column(String, ForeignKey("rooms.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    system: Mapped[str] = mapped_column(String, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    max_players: Mapped[int] = mapped_column(Integer, nullable=False)

    master = relationship("User", back_populates="games")
    room = relationship("Room", back_populates="games")
    enrollments = relationship("Enrollment", back_populates="game", cascade="all, delete-orphan")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(String, ForeignKey("games.id"), nullable=False)
    player_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    game = relationship("Game", back_populates="enrollments")
    player = relationship("User", back_populates="enrollments")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    # Без FK: сповіщення про скасовану гру має пережити видалення самої гри.
    game_id: Mapped[str] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user = relationship("User", back_populates="notifications")
