"""R-15: кеш проксі має межу розміру й не віддає застарілі дані."""

from datetime import datetime, timedelta

import pytest

import store
from models import Game
from store import BoundedCache, DBProxyDict


def add_games(count):
    db = store.SessionLocal()
    try:
        db.add_all(
            [
                Game(
                    id=f"game_{10 + index}",
                    master_id="user_2",
                    room_id="room_3",
                    title=f"Нічна гра {index}",
                    system="GURPS",
                    starts_at=datetime(2026, 11, 1, 10, 0) + timedelta(hours=index * 4),
                    duration_minutes=60,
                    max_players=4,
                )
                for index in range(count)
            ]
        )
        db.commit()
    finally:
        db.close()


@pytest.mark.technical
def test_bounded_cache_evicts_the_least_recently_used_entry():
    cache = BoundedCache(max_entries=2)
    cache["a"] = 1
    cache["b"] = 2
    assert cache.get("a") == 1  # «a» стає найновішим
    cache["c"] = 3

    assert "b" not in cache
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert len(cache) == 2


@pytest.mark.technical
@pytest.mark.parametrize("size", [0, -1])
def test_bounded_cache_rejects_non_positive_size(size):
    with pytest.raises(ValueError):
        BoundedCache(max_entries=size)


@pytest.mark.technical
def test_proxy_cache_never_exceeds_its_limit():
    add_games(6)
    proxy = DBProxyDict(Game, transform_func=store._game_transform, max_cache_entries=3)

    assert len(proxy.values()) == 8
    assert len(proxy._cache) == 3


@pytest.mark.technical
def test_row_changed_outside_the_proxy_is_not_served_from_stale_cache():
    assert store.GAMES["game_1"].title == "Прокляття Страда"  # запис потрапив у кеш

    db = store.SessionLocal()
    try:
        db.query(Game).filter(Game.id == "game_1").update({"title": "Нова назва"})
        db.commit()
    finally:
        db.close()

    # без ручної інвалідації: застарілий об'єкт з кешу не повертається
    assert store.GAMES["game_1"].title == "Нова назва"


@pytest.mark.technical
def test_cached_object_identity_is_kept_while_the_row_is_unchanged():
    assert store.GAMES["game_1"] is store.GAMES["game_1"]


@pytest.mark.technical
def test_invalidate_removes_a_single_entry():
    store.GAMES["game_1"]
    assert "game_1" in store.GAMES._cache

    store.GAMES.invalidate("game_1")

    assert "game_1" not in store.GAMES._cache
