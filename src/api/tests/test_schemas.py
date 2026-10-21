import pytest
from pydantic import ValidationError

from schemas import GameBase, GamePatch, LoginRequest, Pagination, RoomPatch


@pytest.fixture
def valid_game():
    return {
        "title": "Гра",
        "system": "D&",
        "room_id": "room_1",
        "starts_at": "2026-10-10T18:00:00Z",
        "duration_minutes": 30,
        "max_players": 2,
    }


def build(valid_game, **overrides):
    return GameBase(**{**valid_game, **overrides})


def test_title_length_lower_boundary(valid_game):
    with pytest.raises(ValidationError):
        build(valid_game, title="Гр")
    assert build(valid_game, title="Гра").title == "Гра"


@pytest.mark.parametrize("minutes", [30, 31, 719, 720])
def test_duration_accepts_values_inside_range(valid_game, minutes):
    assert build(valid_game, duration_minutes=minutes).duration_minutes == minutes


@pytest.mark.parametrize("minutes", [-1, 0, 29, 721, 10000])
def test_duration_rejects_values_outside_range(valid_game, minutes):
    with pytest.raises(ValidationError):
        build(valid_game, duration_minutes=minutes)


@pytest.mark.parametrize("players", [2, 3, 7, 8])
def test_max_players_accepts_values_inside_range(valid_game, players):
    assert build(valid_game, max_players=players).max_players == players


@pytest.mark.parametrize("players", [0, 1, 9, 100])
def test_max_players_rejects_values_outside_range(valid_game, players):
    with pytest.raises(ValidationError):
        build(valid_game, max_players=players)


def test_title_length_upper_boundary(valid_game):
    assert len(build(valid_game, title="а" * 100).title) == 100
    with pytest.raises(ValidationError):
        build(valid_game, title="а" * 101)


def test_system_length_boundaries(valid_game):
    assert build(valid_game, system="ab").system == "ab"
    with pytest.raises(ValidationError):
        build(valid_game, system="a")
    with pytest.raises(ValidationError):
        build(valid_game, system="a" * 51)


@pytest.mark.parametrize("room_id", ["room_", "room_x", "Room_1", "room_1 ", "1", "room_1\n"])
def test_room_id_pattern_rejects_malformed_values(valid_game, room_id):
    with pytest.raises(ValidationError):
        build(valid_game, room_id=room_id)


def test_starts_at_requires_timezone(valid_game):
    with pytest.raises(ValidationError):
        build(valid_game, starts_at="2026-10-10T18:00:00")


def test_game_base_forbids_extra_fields(valid_game):
    with pytest.raises(ValidationError):
        build(valid_game, color="red")


def test_game_patch_allows_empty_body_and_partial_fields():
    assert GamePatch().model_dump() == {
        "title": None,
        "system": None,
        "room_id": None,
        "starts_at": None,
        "duration_minutes": None,
        "max_players": None,
    }
    assert GamePatch(max_players=8).max_players == 8


def test_game_patch_validates_provided_fields():
    with pytest.raises(ValidationError):
        GamePatch(max_players=9)


@pytest.mark.parametrize(
    "email",
    ["a@b.c", "master@club.test", "first.last@sub.domain.org"],
)
def test_login_request_accepts_valid_email(email):
    assert LoginRequest(email=email, password="12345678").email == email


@pytest.mark.parametrize("email", ["", "a@b", "a b@c.d", "@b.c", "a@@b.c", "abcd"])
def test_login_request_rejects_invalid_email(email):
    with pytest.raises(ValidationError):
        LoginRequest(email=email, password="12345678")


def test_login_request_password_length_boundaries():
    assert LoginRequest(email="a@b.c", password="1" * 8).password == "1" * 8
    assert len(LoginRequest(email="a@b.c", password="1" * 100).password) == 100
    with pytest.raises(ValidationError):
        LoginRequest(email="a@b.c", password="1" * 7)
    with pytest.raises(ValidationError):
        LoginRequest(email="a@b.c", password="1" * 101)


def test_pagination_limit_boundaries():
    assert Pagination(limit=1, offset=0, total=0, has_more=False).limit == 1
    assert Pagination(limit=100, offset=0, total=0, has_more=False).limit == 100
    with pytest.raises(ValidationError):
        Pagination(limit=0, offset=0, total=0, has_more=False)
    with pytest.raises(ValidationError):
        Pagination(limit=101, offset=0, total=0, has_more=False)


def test_room_patch_requires_boolean_and_forbids_extra():
    assert RoomPatch(is_blocked=True).is_blocked is True
    with pytest.raises(ValidationError):
        RoomPatch()
    with pytest.raises(ValidationError):
        RoomPatch(is_blocked=True, name="x")
