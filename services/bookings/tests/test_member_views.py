from datetime import datetime

import pytest

from database.database import (
    get_connection,
    create_scheduling_tables,
    create_booking_tables,
)
from bookings import auth, service
from scheduling import service as scheduling_service

NOW = datetime(2026, 10, 7, 12, 0)


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    create_scheduling_tables(c)
    create_booking_tables(c)
    yield c
    c.close()


def make_member(conn, email):
    return auth.register(conn, "Member", email, "secret123")


def make_session(conn, start, capacity=2):
    class_type = scheduling_service.create_class_type(conn, f"Yoga {start}")
    instructor = scheduling_service.create_instructor(conn, "Sarah")
    return scheduling_service.create_session(conn, class_type, instructor, start, capacity)


def test_get_schedule_shows_spots_left_and_member_status(conn):
    maya = make_member(conn, "maya@example.com")
    other = make_member(conn, "other@example.com")
    open_session = make_session(conn, "2026-10-08T18:00", capacity=2)
    full_session = make_session(conn, "2026-10-09T18:00", capacity=1)
    service.buy_pass(conn, maya, "class_pack", now=NOW)
    service.buy_pass(conn, other, "class_pack", now=NOW)
    service.book_class(conn, maya, open_session, now=NOW)
    service.book_class(conn, other, full_session, now=NOW)
    service.join_waitlist(conn, maya, full_session, now=NOW)

    by_id = {s["id"]: s for s in service.get_schedule(conn, maya, now=NOW)}

    assert by_id[open_session]["spots_left"] == 1
    assert by_id[open_session]["member_status"] == "booked"
    assert by_id[full_session]["spots_left"] == 0
    assert by_id[full_session]["member_status"] == "waitlisted"
    assert by_id[full_session]["waitlist_position"] == 1


def test_get_schedule_for_a_visitor_has_no_member_status(conn):
    make_session(conn, "2026-10-08T18:00")
    item = service.get_schedule(conn, None, now=NOW)[0]
    assert item["member_status"] is None
    assert item["spots_left"] == 2


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