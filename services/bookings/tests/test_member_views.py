from datetime import datetime

import pytest

from bookings import auth, service
from bookings.scheduling_client import SchedulingUnavailable
from tests import scheduling_stub

NOW = datetime(2026, 10, 7, 12, 0)


def make_member(conn, email):
    return auth.register(conn, "Member", email, "secret123")


def make_session(conn, start, capacity=2):
    return scheduling_stub.add_session(start, capacity, class_name=f"Yoga {start}")


def test_availability_shows_spots_taken_and_member_status(conn):
    maya = make_member(conn, "maya@example.com")
    other = make_member(conn, "other@example.com")
    open_session = make_session(conn, "2026-10-08T18:00", capacity=2)
    full_session = make_session(conn, "2026-10-09T18:00", capacity=1)
    service.buy_pass(conn, maya, "class_pack", now=NOW)
    service.buy_pass(conn, other, "class_pack", now=NOW)
    service.book_class(conn, maya, open_session, now=NOW)
    service.book_class(conn, other, full_session, now=NOW)
    service.join_waitlist(conn, maya, full_session, now=NOW)

    result = service.get_availability(conn, [open_session, full_session], maya)

    assert result[open_session] == {"booked": 1, "member_status": "booked", "waitlist_position": None}
    assert result[full_session] == {"booked": 1, "member_status": "waitlisted", "waitlist_position": 1}


def test_availability_for_a_visitor_has_no_member_status(conn):
    session_id = make_session(conn, "2026-10-08T18:00")
    result = service.get_availability(conn, [session_id], None)
    assert result[session_id] == {"booked": 0, "member_status": None, "waitlist_position": None}


def test_list_member_bookings_has_names_and_can_cancel_flag(conn):
    maya = make_member(conn, "maya@example.com")
    session_id = make_session(conn, "2026-10-08T18:00")
    service.buy_pass(conn, maya, "class_pack", now=NOW)
    service.book_class(conn, maya, session_id, now=NOW)

    before = service.list_member_bookings(conn, maya, now=NOW)[0]
    after = service.list_member_bookings(conn, maya, now=datetime(2026, 10, 9))[0]

    assert before["class_name"] == "Yoga 2026-10-08T18:00"
    assert before["instructor_name"] == "Sarah"
    assert before["can_cancel"] is True
    assert after["can_cancel"] is False


def test_list_member_bookings_is_sorted_soonest_first(conn):
    maya = make_member(conn, "maya@example.com")
    later = make_session(conn, "2026-10-10T18:00")
    sooner = make_session(conn, "2026-10-08T18:00")
    service.buy_pass(conn, maya, "class_pack", now=NOW)
    service.book_class(conn, maya, later, now=NOW)
    service.book_class(conn, maya, sooner, now=NOW)

    ids = [b["session_id"] for b in service.list_member_bookings(conn, maya, now=NOW)]

    assert ids == [sooner, later]


def test_list_member_waitlist_shows_position(conn):
    owner = make_member(conn, "owner@example.com")
    waiting = make_member(conn, "waiting@example.com")
    session_id = make_session(conn, "2026-10-08T18:00", capacity=1)
    service.buy_pass(conn, owner, "drop_in", now=NOW)
    service.book_class(conn, owner, session_id, now=NOW)
    service.join_waitlist(conn, waiting, session_id, now=NOW)

    entries = service.list_member_waitlist(conn, waiting)

    assert len(entries) == 1
    assert entries[0]["position"] == 1
    assert entries[0]["session_id"] == session_id
    assert entries[0]["class_name"] == "Yoga 2026-10-08T18:00"


def test_list_member_passes_marks_validity(conn):
    maya = make_member(conn, "maya@example.com")
    service.buy_pass(conn, maya, "drop_in", now=NOW)
    service.buy_pass(conn, maya, "membership", now=datetime(2026, 1, 1))  # long expired

    passes = {p["type"]: p for p in service.list_member_passes(conn, maya, now=NOW)}

    assert passes["drop_in"]["is_valid"] is True
    assert passes["membership"]["is_valid"] is False

# ---------- partial failure: Scheduling can't be reached ----------

def test_bookings_are_still_listed_without_details_when_scheduling_is_down(conn):
    maya = make_member(conn, "maya@example.com")
    first = make_session(conn, "2026-10-08T18:00")
    second = make_session(conn, "2026-10-09T18:00")
    service.buy_pass(conn, maya, "class_pack", now=NOW)
    service.book_class(conn, maya, first, now=NOW)
    service.book_class(conn, maya, second, now=NOW)
    scheduling_stub.down = True

    bookings = service.list_member_bookings(conn, maya, now=NOW)

    assert {b["session_id"] for b in bookings} == {first, second}
    assert all(b["details_available"] is False for b in bookings)
    assert all(b["can_cancel"] is False for b in bookings)


def test_waitlist_is_still_listed_without_details_when_scheduling_is_down(conn):
    owner = make_member(conn, "owner@example.com")
    waiting = make_member(conn, "waiting@example.com")
    session_id = make_session(conn, "2026-10-08T18:00", capacity=1)
    service.buy_pass(conn, owner, "drop_in", now=NOW)
    service.book_class(conn, owner, session_id, now=NOW)
    service.join_waitlist(conn, waiting, session_id, now=NOW)
    scheduling_stub.down = True

    entries = service.list_member_waitlist(conn, waiting)

    assert entries[0]["details_available"] is False
    assert entries[0]["position"] == 1


def test_booking_whose_session_was_removed_is_shown_without_details(conn):
    maya = make_member(conn, "maya@example.com")
    gone = make_session(conn, "2026-10-08T18:00")
    kept = make_session(conn, "2026-10-09T18:00")
    service.buy_pass(conn, maya, "class_pack", now=NOW)
    service.book_class(conn, maya, gone, now=NOW)
    service.book_class(conn, maya, kept, now=NOW)
    del scheduling_stub.sessions[gone]  # Scheduling no longer knows this session

    by_id = {b["session_id"]: b for b in service.list_member_bookings(conn, maya, now=NOW)}

    assert by_id[gone]["details_available"] is False
    assert by_id[kept]["details_available"] is True


def test_booking_fails_clearly_when_scheduling_is_down(conn):
    maya = make_member(conn, "maya@example.com")
    session_id = make_session(conn, "2026-10-08T18:00")
    service.buy_pass(conn, maya, "class_pack", now=NOW)
    scheduling_stub.down = True

    with pytest.raises(SchedulingUnavailable):
        service.book_class(conn, maya, session_id, now=NOW)
    assert service.list_member_bookings(conn, maya, now=NOW) == []  # nothing was written
