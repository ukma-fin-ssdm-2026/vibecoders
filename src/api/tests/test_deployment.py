"""Налаштування розгортання: CORS для Swagger UI на GitHub Pages і адреса сервера в специфікації."""

import pytest

PAGES_ORIGIN = "https://ukma-fin-ssdm-2026.github.io"


@pytest.mark.technical
def test_preflight_from_github_pages_is_allowed(client):
    response = client.options(
        "/api/v1/games",
        headers={
            "Origin": PAGES_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


@pytest.mark.technical
def test_preflight_from_foreign_origin_is_rejected(client):
    response = client.options(
        "/api/v1/games",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.technical
def test_actual_response_exposes_retry_after_and_location_to_browser(client):
    response = client.get("/api/v1/games", headers={"Origin": PAGES_ORIGIN})
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "retry-after" in exposed and "location" in exposed


@pytest.mark.technical
def test_openapi_first_server_is_public_not_localhost(client):
    servers = client.get("/openapi.json").json()["servers"]
    assert servers[0]["url"].startswith("https://")
    assert any("localhost" in server["url"] for server in servers)
