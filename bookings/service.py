import sqlite3
from datetime import datetime, timedelta

from bookings import events, repository, strategies
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

    session = _get_open_session(conn, session_id, now)

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

def get_waitlist_position(conn, member_id, session_id):
    """1 = first in line, or None if the member is not on the waitlist."""
    entry = repository.get_waitlist_entry(conn, member_id, session_id)
    if entry is None:
        return None
    return repository.count_waitlist_up_to(conn, session_id, entry["id"])


def join_waitlist(conn, member_id, session_id, now=None):
    now = now or datetime.now()

    if repository.get_member_by_id(conn, member_id) is None:
        raise BookingError("Member does not exist")
    session = _get_open_session(conn, session_id, now)

    if repository.get_confirmed_booking(conn, member_id, session_id):
        raise BookingError("You already have a booking for this session")
    if repository.count_confirmed_bookings(conn, session_id) < session["capacity"]:
        raise BookingError("This session still has free spots, book it instead")

    try:
        repository.add_waitlist_entry(conn, member_id, session_id)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise BookingError("You are already on the waitlist for this session")
    return get_waitlist_position(conn, member_id, session_id)


def leave_waitlist(conn, member_id, session_id):
    entry = repository.get_waitlist_entry(conn, member_id, session_id)
    if entry is None:
        raise BookingError("You are not on the waitlist for this session")
    repository.remove_waitlist_entry(conn, entry["id"])
    conn.commit()


def book_or_join_waitlist(conn, member_id, session_id, now=None):
    """What the 'Book' button calls: a booking if there is room, else a waitlist spot."""
    try:
        booking_id = book_class(conn, member_id, session_id, now=now)
        return {"status": "confirmed", "booking_id": booking_id}
    except SessionFullError:
        position = join_waitlist(conn, member_id, session_id, now=now)
        return {"status": "waitlisted", "position": position}


def cancel_booking(conn, member_id, booking_id, now=None, bus=None):
    """Free cancellation any time before the session starts (rule 6)."""
    now = now or datetime.now()

    booking = repository.get_booking(conn, booking_id)
    if booking is None or booking["member_id"] != member_id:
        raise BookingError("Booking not found")
    if booking["status"] != "confirmed":
        raise BookingError("This booking is already cancelled")

    session = scheduling_service.get_session_info(conn, booking["session_id"])
    if session["start_time"] <= now.isoformat(timespec="seconds"):
        raise BookingError("This session has already started")

    pass_row = dict(repository.get_pass(conn, booking["pass_id"]))
    strategy = strategies.get_strategy(pass_row["type"])
    try:
        # Two changes that must succeed together: cancel the booking + give the credit back
        repository.set_booking_status(conn, booking_id, "cancelled")
        repository.set_pass_remaining(
            conn, pass_row["id"], strategy.remaining_after_refund(pass_row)
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise

    # The cancellation is saved. Now announce it; whoever subscribed reacts.
    event = events.BookingCancelled(
        booking_id=booking_id, member_id=member_id, session_id=booking["session_id"]
    )
    bus = bus if bus is not None else events.default_bus
    bus.publish(event, conn, now)

    return {
        "booking_id": booking_id,
        "member_id": member_id,
        "session_id": booking["session_id"],
    }

def promote_next_from_waitlist(conn, session_id, now=None):
    """Give a free spot to the first waitlisted member who can take it.

    Returns {"member_id", "booking_id", "session_id"}, or None if nobody was promoted.
    """
    now = now or datetime.now()

    try:
        session = _get_open_session(conn, session_id, now)
    except BookingError:
        return None  # session was cancelled by the studio, already started, or is gone
    if repository.count_confirmed_bookings(conn, session_id) >= session["capacity"]:
        return None  # no free spot

    while True:
        entry = repository.get_first_waitlist_entry(conn, session_id)
        if entry is None:
            return None
        member_id = entry["member_id"]

        already_booked = repository.get_confirmed_booking(conn, member_id, session_id)
        pass_row = None if already_booked else find_usable_pass(conn, member_id, now)
        if already_booked or pass_row is None:
            # Can't be promoted: take them off the list and try the next person
            repository.remove_waitlist_entry(conn, entry["id"])
            conn.commit()
            continue

        strategy = strategies.get_strategy(pass_row["type"])
        try:
            # Three changes that must succeed together
            repository.remove_waitlist_entry(conn, entry["id"])
            repository.set_pass_remaining(
                conn, pass_row["id"], strategy.remaining_after_use(pass_row)
            )
            booking_id = repository.add_booking(
                conn, member_id, session_id, pass_row["id"]
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        return {"member_id": member_id, "booking_id": booking_id, "session_id": session_id}


def _on_booking_cancelled(event, conn, now):
    """Observer: when a booking is cancelled, offer its spot to the waitlist."""
    promote_next_from_waitlist(conn, event.session_id, now=now)


events.default_bus.subscribe(events.BookingCancelled, _on_booking_cancelled)


# helper function to see if the session exists and is still open 

def _get_open_session(conn, session_id, now):
    """Ask Scheduling (through its service) for a session that can be booked."""
    try:
        session = scheduling_service.get_session_info(conn, session_id)
        is_open = scheduling_service.is_open_for_booking(conn, session_id, now=now)
    except SchedulingError:
        raise BookingError("Session does not exist")
    if not is_open:
        raise BookingError("This session is not open for booking")
    return session