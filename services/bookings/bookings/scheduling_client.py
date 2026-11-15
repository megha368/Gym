"""How the Bookings service talks to the Scheduling service.

Before the split, Bookings imported Scheduling's code directly. Now Scheduling is a
separate program, so Bookings sends it HTTP requests instead. Everything that crosses
the seam goes through this one file.
"""

from datetime import datetime

import requests

from config.settings import SCHEDULING_TIMEOUT_S, SCHEDULING_URL


class SessionNotFound(Exception):
    """Scheduling answered, and said the session doesn't exist (HTTP 404)."""


class SchedulingUnavailable(Exception):
    """Scheduling didn't answer in time, couldn't be reached, or returned an error."""


def _get(path, params=None):
    try:
        response = requests.get(
            f"{SCHEDULING_URL}{path}", params=params, timeout=SCHEDULING_TIMEOUT_S
        )
    except requests.RequestException as error:  # timeout, connection refused, ...
        raise SchedulingUnavailable(f"Scheduling service unreachable: {error}") from error
    if response.status_code == 404:
        raise SessionNotFound(response.json().get("error", "Session does not exist"))
    if response.status_code != 200:
        raise SchedulingUnavailable(f"Scheduling service returned {response.status_code}")
    return response.json()


def get_session(session_id):
    """One session: id, class_name, instructor_name, start_time, capacity, status."""
    return _get(f"/sessions/{session_id}")


def list_upcoming_sessions(now=None):
    """Scheduled sessions starting from `now`, soonest first."""
    now = now or datetime.now()
    return _get("/sessions", params={"from": now.isoformat(timespec="seconds")})


def is_open_for_booking(session, now=None):
    """A session can be booked if it is still scheduled and hasn't started yet."""
    now = now or datetime.now()
    return (
        session["status"] == "scheduled"
        and session["start_time"] > now.isoformat(timespec="seconds")
    )
