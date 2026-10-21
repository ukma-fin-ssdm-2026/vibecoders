import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from errors import ApiError, error_docs, error_response, register_error_handlers
from schemas import ErrorDetail, ErrorResponse


def test_api_error_defaults_details_to_empty_list():
    error = ApiError(404, "NOT_FOUND", "немає")
    assert error.details == []
    assert error.headers is None
    assert (error.status_code, error.code, error.message) == (404, "NOT_FOUND", "немає")


def test_error_response_builds_envelope_with_details():
    detail = ErrorDetail(field="body.title", message="too short")
    response = error_response(400, "VALIDATION_ERROR", "bad", [detail], headers={"X-Test": "1"})
    body = json.loads(response.body)
    assert response.status_code == 400
    assert response.headers["x-test"] == "1"
    assert body == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "bad",
            "details": [{"field": "body.title", "message": "too short"}],
        }
    }


def test_error_response_without_details_returns_empty_list():
    body = json.loads(error_response(409, "CONFLICT", "x").body)
    assert body["error"]["details"] == []
    ErrorResponse(**body)


def test_error_docs_maps_codes_to_models():
    docs = error_docs(400, 404)
    assert set(docs) == {400, 404}
    assert docs[404]["model"] is ErrorResponse
    assert docs[400]["description"]


def test_error_docs_rejects_unknown_code():
    with pytest.raises(KeyError):
        error_docs(418)


def test_validation_error_is_reported_with_field_paths(client, master_headers, game_payload):
    game_payload["max_players"] = 9
    response = client.post("/api/v1/games", json=game_payload, headers=master_headers)
    body = response.json()
    assert response.status_code == 400
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "body.max_players"


def test_unknown_route_uses_not_found_envelope(client):
    response = client.get("/api/v1/nothing-here")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_wrong_method_uses_method_not_allowed_envelope(client):
    response = client.put("/api/v1/rooms")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_unexpected_exception_is_converted_to_500_envelope():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in response.text


def test_api_error_headers_are_forwarded():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/denied")
    async def denied():
        raise ApiError(401, "UNAUTHORIZED", "no", headers={"WWW-Authenticate": "Bearer"})

    response = TestClient(app).get("/denied")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
