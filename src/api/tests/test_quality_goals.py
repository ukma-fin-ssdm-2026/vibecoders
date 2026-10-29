"""Тести, що перевіряють числові межі з docs/api/quality-attributes.md."""

from datetime import datetime, timedelta, timezone

import pytest
import yaml

import spec
from booking_db import BookingRepository, SlotTakenError
from main import app
from store import CREDENTIALS

DEMO_LOGINS = {
    "master@club.test": "master-pass-1",
    "player@club.test": "player-pass-1",
    "owner@club.test": "owner-pass-1",
}


@pytest.mark.requirement("REL-002")
def test_hundred_overlapping_attempts_of_one_master_are_all_rejected(tmp_path):
    repo = BookingRepository(str(tmp_path / "bookings.db"))
    start = datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc)
    repo.book("room_1", "user_1", start, 120)
    rejected = 0
    for minutes in range(100):
        try:
            repo.book("room_2", "user_1", start + timedelta(minutes=minutes), 30)
        except SlotTakenError:
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