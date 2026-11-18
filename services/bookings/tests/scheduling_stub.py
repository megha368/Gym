"""A stand-in for the Scheduling service, used by Bookings' unit tests.

Bookings only reaches Scheduling through bookings/scheduling_client.py, so the tests
replace that file's functions with the ones below (see conftest.py). They answer from a
dictionary instead of sending HTTP requests, which keeps Bookings' unit tests fast and
independent of Scheduling. The real HTTP path is covered by the integration test in
tests/integration at the root of the repository.

Set `scheduling_stub.down = True` to pretend Scheduling can't be reached.
"""

from datetime import datetime

from bookings.scheduling_client import SchedulingUnavailable, SessionNotFound

sessions = {}
down = False
_next_id = 1


def reset():
    global down, _next_id
    sessions.clear()
    down = False
    _next_id = 1


def add_session(start="2026-10-08T18:00", capacity=5, class_name="Yoga",
                instructor_name="Sarah", status="scheduled"):
    """Pretend Scheduling has this session; returns its id."""
    global _next_id
    session_id = _next_id
    _next_id += 1
    sessions[session_id] = {
        "id": session_id,
        "class_name": class_name,
        "instructor_name": instructor_name,
        # like the real Scheduling: always "YYYY-MM-DDTHH:MM:SS"
        "start_time": datetime.fromisoformat(start).isoformat(timespec="seconds"),
        "capacity": capacity,
        "status": status,
    }
    return session_id


def cancel_session(session_id):
    sessions[session_id]["status"] = "cancelled"


# ----- the same functions as bookings/scheduling_client.py -----

def get_session(session_id):
    if down:
        raise SchedulingUnavailable("stub: Scheduling is down")
    if session_id not in sessions:
        raise SessionNotFound("Session does not exist")
    return dict(sessions[session_id])


def list_upcoming_sessions(now=None):
    if down:
        raise SchedulingUnavailable("stub: Scheduling is down")
    upcoming = [dict(s) for s in sessions.values() if s["status"] == "scheduled"]
    if now is not None:
        upcoming = [s for s in upcoming if s["start_time"] > now.isoformat(timespec="seconds")]
    return sorted(upcoming, key=lambda s: s["start_time"])
