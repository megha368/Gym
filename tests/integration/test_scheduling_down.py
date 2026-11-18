"""Partial failure, with the Scheduling container stopped:

    docker compose stop scheduling
    EXPECT_SCHEDULING_DOWN=1 pytest tests/integration
    docker compose start scheduling

Bookings must keep serving its own data and fail clearly (503) where it needs Scheduling.
"""

import os

import pytest
import requests

from conftest import BOOKINGS_URL, TIMEOUT_S

pytestmark = pytest.mark.skipif(
    os.environ.get("EXPECT_SCHEDULING_DOWN") != "1", reason="run with Scheduling stopped"
)


def test_bookings_stays_healthy_when_scheduling_is_down():
    assert requests.get(f"{BOOKINGS_URL}/health", timeout=TIMEOUT_S).status_code == 200


def test_own_data_still_works_and_booking_fails_clearly(member):
    assert requests.get(f"{BOOKINGS_URL}/passes", headers=member, timeout=TIMEOUT_S).status_code == 200
    assert requests.get(f"{BOOKINGS_URL}/bookings", headers=member, timeout=TIMEOUT_S).status_code == 200

    response = requests.post(f"{BOOKINGS_URL}/bookings", json={"session_id": 1}, headers=member, timeout=TIMEOUT_S)
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["error"]
