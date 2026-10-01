import sqlite3
from datetime import datetime

from scheduling import repository


class SchedulingError(Exception):
    """Raised when a scheduling rule is broken."""


def _parse_time(value):
    try:
        return datetime.fromisoformat(value).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        raise SchedulingError("start_time must be an ISO datetime like 2026-10-07T18:00")


def create_class_type(conn, name, description=None):
    name = (name or "").strip()
    if not name:
        raise SchedulingError("Class type name is required")
    try:
        return repository.add_class_type(conn, name, description)
    except sqlite3.IntegrityError:
        raise SchedulingError(f"Class type '{name}' already exists")


def create_instructor(conn, name):
    name = (name or "").strip()
    if not name:
        raise SchedulingError("Instructor name is required")
    return repository.add_instructor(conn, name)


def create_session(conn, class_type_id, instructor_id, start_time, capacity):
    if repository.get_class_type(conn, class_type_id) is None:
        raise SchedulingError("Class type does not exist")
    if repository.get_instructor(conn, instructor_id) is None:
        raise SchedulingError("Instructor does not exist")
    if not isinstance(capacity, int) or capacity < 1:
        raise SchedulingError("Capacity must be a whole number of at least 1")
    start_time = _parse_time(start_time)
    return repository.add_session(conn, class_type_id, instructor_id, start_time, capacity)


def list_upcoming_sessions(conn, now=None):
    now = now or datetime.now()
    rows = repository.list_scheduled_sessions_from(conn, now.isoformat(timespec="seconds"))
    return [dict(r) for r in rows]


def get_session_info(conn, session_id):
    """The interface the Bookings domain uses to ask about a session."""
    row = repository.get_session(conn, session_id)
    if row is None:
        raise SchedulingError("Session does not exist")
    return dict(row)


def is_open_for_booking(conn, session_id, now=None):
    now = now or datetime.now()
    session = get_session_info(conn, session_id)
    return (
        session["status"] == "scheduled"
        and session["start_time"] > now.isoformat(timespec="seconds")
    )


def cancel_session(conn, session_id):
    session = get_session_info(conn, session_id)
    if session["status"] == "cancelled":
        raise SchedulingError("Session is already cancelled")
    repository.set_session_status(conn, session_id, "cancelled")