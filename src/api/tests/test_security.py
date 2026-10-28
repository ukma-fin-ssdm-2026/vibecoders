from unittest.mock import MagicMock

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from errors import ApiError
from schemas import UserRole
from security import get_current_user, require_roles
from store import USERS


def make_credentials(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.parametrize(
    "token, user_id",
    [("master-token", "user_1"), ("player-token", "user_2"), ("owner-token", "user_3")],
)
@pytest.mark.requirement("SEC-002")
def test_get_current_user_resolves_known_tokens(token, user_id):
    assert get_current_user(make_credentials(token)) is USERS[user_id]


@pytest.mark.requirement("SEC-002")
def test_get_current_user_rejects_missing_credentials():
    with pytest.raises(ApiError) as error:
        get_current_user(None)
    assert error.value.status_code == 401
    assert error.value.code == "UNAUTHORIZED"
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.parametrize("token", ["", "unknown", "MASTER-TOKEN", " master-token"])
@pytest.mark.requirement("SEC-002")
def test_get_current_user_rejects_invalid_tokens(token):
    with pytest.raises(ApiError) as error:
        get_current_user(make_credentials(token))
    assert error.value.status_code == 401


@pytest.mark.requirement("SEC-002")
def test_get_current_user_uses_token_lookup_table(monkeypatch):
    import security

    stub_user = MagicMock(name="stub_user")
    monkeypatch.setattr(security, "TOKENS", {"stub-token": "stub_id"})
    monkeypatch.setattr(security, "USERS", {"stub_id": stub_user})
    assert get_current_user(make_credentials("stub-token")) is stub_user


@pytest.mark.requirement("SEC-002")
def test_require_roles_allows_listed_role():
    require_roles(USERS["user_1"], UserRole.master, UserRole.owner)


@pytest.mark.requirement("SEC-002")
def test_require_roles_rejects_unlisted_role():
    with pytest.raises(ApiError) as error:
        require_roles(USERS["user_2"], UserRole.master, UserRole.owner)
    assert error.value.status_code == 403
    assert error.value.code == "FORBIDDEN"


@pytest.mark.requirement("SEC-002")
def test_require_roles_without_roles_rejects_everyone():
    with pytest.raises(ApiError):
        require_roles(USERS["user_3"])


@pytest.mark.requirement("SEC-002")
def test_protected_endpoint_without_token_returns_401(client, game_payload):
    response = client.post("/api/v1/games", json=game_payload)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.requirement("SEC-002")
def test_protected_endpoint_with_wrong_scheme_returns_401(client, game_payload):
    response = client.post("/api/v1/games", json=game_payload, headers={"Authorization": "Basic master-token"})
    assert response.status_code == 401
