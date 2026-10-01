import sqlite3
from datetime import datetime, timedelta

from bookings import repository, strategies
from scheduling import service as scheduling_service
from scheduling.service import SchedulingError


class BookingError(Exception):
    """Raised when a booking rule is broken."""


class SessionFullError(BookingError):
    """The session has no free spots (Day 4: caller offers the waitlist)."""


# What each pass type looks like when a member buys it
PASS_DEFAULTS = {
    "drop_in": {"uses": 1, "valid_days": None},
    "class_pack": {"uses": 10, "valid_days": 90},
    "membership": {"uses": None, "valid_days": 30},
}


def buy_pass(conn, member_id, pass_type, now=None):
    now = now or datetime.now()
    if pass_type not in PASS_DEFAULTS:
        raise BookingError(f"Unknown pass type: {pass_type}")
    if repository.get_member_by_id(conn, member_id) is None:
        raise BookingError("Member does not exist")

    defaults = PASS_DEFAULTS[pass_type]
    expires_at = None
    if defaults["valid_days"] is not None:
        expires_at = (now + timedelta(days=defaults["valid_days"])).isoformat(
            timespec="seconds"
        )
    return repository.add_pass(conn, member_id, pass_type, defaults["uses"], expires_at)


def find_usable_pass(conn, member_id, now):
    """The member's best valid pass (membership > class pack > drop-in), or None."""
    passes = [dict(p) for p in repository.list_passes_for_member(conn, member_id)]
    usable = [
        p for p in passes
        if strategies.get_strategy(p["type"]).is_valid(p, now)
    ]
    if not usable:
        return None
    return min(usable, key=lambda p: strategies.get_strategy(p["type"]).priority)


def book_class(conn, member_id, session_id, now=None):
    now = now or datetime.now()

    if repository.get_member_by_id(conn, member_id) is None:
        raise BookingError("Member does not exist")

    # Ask the Scheduling domain about the session, only through its service
    try:
        is_open = scheduling_service.is_open_for_booking(conn, session_id, now=now)
        session = scheduling_service.get_session_info(conn, session_id)
    except SchedulingError:
        raise BookingError("Session does not exist")
    if not is_open:
        raise BookingError("This session is not open for booking")

    if repository.get_confirmed_booking(conn, member_id, session_id):
        raise BookingError("You already have a booking for this session")

    if repository.count_confirmed_bookings(conn, session_id) >= session["capacity"]:
        raise SessionFullError("This session is full")

    pass_row = find_usable_pass(conn, member_id, now)
    if pass_row is None:
        raise BookingError("You have no valid pass for this booking")

    strategy = strategies.get_strategy(pass_row["type"])
    try:
        # Two changes that must succeed together: use up the pass + create the booking
        repository.set_pass_remaining(
            conn, pass_row["id"], strategy.remaining_after_use(pass_row)
        )
        booking_id = repository.add_booking(conn, member_id, session_id, pass_row["id"])
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise BookingError("You already have a booking for this session")
    return booking_id


def list_member_bookings(conn, member_id):
    """A member's confirmed bookings, with session details from Scheduling."""
    result = []
    for booking in repository.list_confirmed_bookings_for_member(conn, member_id):
        info = scheduling_service.get_session_info(conn, booking["session_id"])
        result.append({
            "booking_id": booking["id"],
            "session_id": booking["session_id"],
            "start_time": info["start_time"],
            "session_status": info["status"],
        })
    return result