"""Тести, що перевіряють числові межі з docs/api/quality-attributes.md."""

import pytest
import yaml

import spec
from main import app
from store import CREDENTIALS

DEMO_LOGINS = {
    "master@club.test": "master-pass-1",
    "player@club.test": "player-pass-1",
    "owner@club.test": "owner-pass-1",
}


@pytest.mark.requirement("REL-002")
def test_hundred_overlapping_attempts_of_one_master_are_all_rejected(client, master_headers, game_payload):
    rejected = 0
    for minute in range(100):
        game_payload.update(room_id="room_3", starts_at=f"2026-10-10T{18 + minute // 60}:{minute % 60:02d}:00Z")
        response = client.post("/api/v1/games", json=game_payload, headers=master_headers)
        if response.status_code == 409 and response.json()["error"]["code"] == "MASTER_BUSY":
            rejected += 1
    assert rejected == 100


@pytest.mark.requirement("SEC-001")
def test_no_demo_password_is_stored_or_returned_in_plain_text(client):
    for email, password in DEMO_LOGINS.items():
        assert password not in CREDENTIALS[email].values()
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert password not in response.text


@pytest.mark.technical
def test_committed_openapi_yaml_matches_spec_generated_from_code():
    with open(spec.SPEC_PATH, encoding="utf-8") as file:
        committed = yaml.safe_load(file)
    assert committed == yaml.safe_load(yaml.safe_dump(app.openapi(), sort_keys=False, allow_unicode=True))