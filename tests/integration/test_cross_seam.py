"""Flows that cross the seam, with both services running for real."""

import os

import pytest
import requests

from conftest import BOOKINGS_URL, SCHEDULING_URL, TIMEOUT_S

pytestmark = pytest.mark.skipif(
    os.environ.get("EXPECT_SCHEDULING_DOWN") == "1", reason="these need both services running"
)


def an_open_session():
    """An upcoming session with free spots, found through Scheduling and Bookings."""
    sessions = requests.get(f"{SCHEDULING_URL}/sessions", timeout=TIMEOUT_S).json()
    assert sessions, "Scheduling has no upcoming sessions (is SEED_DEMO_DATA on?)"
    ids = ",".join(str(s["id"]) for s in sessions)
    taken = requests.get(f"{BOOKINGS_URL}/availability?session_ids={ids}", timeout=TIMEOUT_S).json()["sessions"]
    for session in sessions:
        if taken[str(session["id"])]["booked"] < session["capacity"]:
            return session
    pytest.fail("no session with free spots")


def test_both_services_are_healthy():
    for url in (SCHEDULING_URL, BOOKINGS_URL):
        response = requests.get(f"{url}/health", timeout=TIMEOUT_S)
        assert response.status_code == 200
        assert response.json()["db"] == "ok"


def test_booking_crosses_the_seam(member):
    """Bookings asks Scheduling about the session before booking, then shows Scheduling's
    class name and time in the member's bookings."""
    session = an_open_session()

    booked = requests.post(f"{BOOKINGS_URL}/bookings", json={"session_id": session["id"]}, headers=member, timeout=TIMEOUT_S)
    assert booked.status_code == 201, booked.text
    assert booked.json()["status"] == "confirmed"

    mine = requests.get(f"{BOOKINGS_URL}/bookings", headers=member, timeout=TIMEOUT_S).json()
    assert mine["details_missing"] is False
    [booking] = [b for b in mine["bookings"] if b["session_id"] == session["id"]]
    assert booking["class_name"] == session["class_name"]
    assert booking["start_time"] == session["start_time"]


def test_booking_a_session_scheduling_does_not_know_is_rejected(member):
    response = requests.post(f"{BOOKINGS_URL}/bookings", json={"session_id": 99999999}, headers=member, timeout=TIMEOUT_S)
    assert response.status_code == 400
    assert response.json()["error"] == "Session does not exist"
