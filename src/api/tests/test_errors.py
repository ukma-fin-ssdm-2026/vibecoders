import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from errors import (
    ERROR_DESCRIPTIONS,
    ApiError,
    error_docs,
    error_response,
    register_error_handlers,
)
from schemas import ErrorDetail, ErrorResponse


def test_api_error_stores_all_attributes():
    details = [ErrorDetail(field="body.max_players", message="too big")]
    err = ApiError(400, "VALIDATION_ERROR", "Погані дані", details=details, headers={"X-A": "1"})
    assert err.status_code == 400
    assert err.code == "VALIDATION_ERROR"
    assert err.message == "Погані дані"
    assert err.details == details
    assert err.headers == {"X-A": "1"}


def test_api_error_defaults_to_empty_details_and_no_headers():
    err = ApiError(403, "FORBIDDEN", "Заборонено")
    assert err.details == []
    assert err.headers is None


def test_api_error_is_an_exception():
    assert issubclass(ApiError, Exception)


def test_api_error_default_details_are_not_shared_between_instances():
    first, second = ApiError(400, "A", "a"), ApiError(400, "B", "b")
    first.details.append(ErrorDetail(field="f", message="m"))
    assert second.details == []


def test_error_response_builds_expected_json_body_and_status():
    details = [ErrorDetail(field="body.title", message="too short")]
    response = error_response(400, "VALIDATION_ERROR", "Невалідно", details)
    body = json.loads(response.body)
    assert response.status_code == 400
    assert body == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Невалідно",
            "details": [{"field": "body.title", "message": "too short"}],
        }
    }


def test_error_response_without_details_returns_empty_list():
    body = json.loads(error_response(404, "NOT_FOUND", "Немає").body)
    assert body["error"]["details"] == []


def test_error_response_passes_headers_through():
    response = error_response(401, "UNAUTHORIZED", "Ні", headers={"WWW-Authenticate": "Bearer"})
    assert response.headers["www-authenticate"] == "Bearer"


def test_error_docs_returns_model_and_description_per_code():
    docs = error_docs(401, 403)
    assert set(docs) == {401, 403}
    for code, entry in docs.items():
        assert entry["model"] is ErrorResponse
        assert entry["description"] == ERROR_DESCRIPTIONS[code]


def test_error_docs_without_codes_is_empty():
    assert error_docs() == {}


def test_error_docs_unknown_code_raises_key_error():
    with pytest.raises(KeyError):
        error_docs(500)


@pytest.fixture
def client():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/api-error")
    def api_error():
        raise ApiError(
            409,
            "ROOM_BUSY",
            "Кімната зайнята",
            details=[ErrorDetail(field="body.room_id", message="busy")],
            headers={"X-Test": "1"},
        )

    @app.get("/validate")
    def validate(x: int):
        return {"x": x}

    @app.get("/teapot")
    def teapot():
        raise StarletteHTTPException(418, "I'm a teapot")

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal info")

    return TestClient(app, raise_server_exceptions=False)


def test_handler_api_error_returns_status_body_and_headers(client):
    response = client.get("/api-error")
    assert response.status_code == 409
    assert response.headers["x-test"] == "1"
    assert response.json() == {
        "error": {
            "code": "ROOM_BUSY",
            "message": "Кімната зайнята",
            "details": [{"field": "body.room_id", "message": "busy"}],
        }
    }


@pytest.mark.parametrize("url", ["/validate?x=abc", "/validate"])
def test_handler_validation_error_returns_400_with_field_path(client, url):
    response = client.get(url)
    error = response.json()["error"]
    assert response.status_code == 400
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["field"] == "query.x"
    assert error["details"][0]["message"]


def test_handler_unknown_route_returns_404_not_found(client):
    response = client.get("/no-such-route")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_handler_wrong_method_returns_405(client):
    response = client.post("/validate")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_handler_other_http_exception_uses_generic_http_error_code(client):
    response = client.get("/teapot")
    assert response.status_code == 418
    assert response.json()["error"]["code"] == "HTTP_ERROR"
    assert response.json()["error"]["message"] == "I'm a teapot"


def test_handler_unexpected_exception_returns_500_without_leaking_details(client):
    response = client.get("/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internal info" not in response.text
