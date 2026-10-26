"""Нефункціональний тест PERF-001: оновлення лічильника місць після запису не довше 1 с.

Вимога описує клієнта, тому на рівні API перевіряється серверна частина:
запис гравця (POST) і наступне читання лічильника (GET) разом мають вкластися в поріг.
"""

from store import ENROLLMENTS

PERF_001_THRESHOLD_SECONDS = 1.0
GAME_URL = "/api/v1/games/game_2"


def test_enroll_and_counter_refresh_fit_into_one_second(benchmark, client, player_headers):
    def reset_enrollments():
        ENROLLMENTS["game_2"] = []

    def enroll_and_read_counter():
        assert client.post(f"{GAME_URL}/players", headers=player_headers).status_code == 201
        return client.get(GAME_URL).json()["current_players"]

    counter = benchmark.pedantic(
        enroll_and_read_counter,
        setup=reset_enrollments,
        rounds=50,
        iterations=1,
    )

    assert counter == 1
    assert benchmark.stats["max"] < PERF_001_THRESHOLD_SECONDS
