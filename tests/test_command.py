from datetime import datetime

import pytest

from database.database import (
    get_connection,
    create_scheduling_tables,
    create_booking_tables,
)
from bookings import auth, events, repository, service
from bookings.commands import BookCommand, CancelCommand, run_command
from bookings.service import BookingError
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


def make_session(conn, capacity=1):
    class_type = scheduling_service.create_class_type(conn, "Yoga")
    instructor = scheduling_service.create_instructor(conn, "Sarah")
    return scheduling_service.create_session(
        conn, class_type, instructor, "2026-10-08T18:00", capacity
    )


def actions(conn):
    return [row["action"] for row in repository.list_audit_entries(conn)]


def test_book_command_books_and_logs_it(conn):
    member = make_member(conn, "a@example.com")
    session_id = make_session(conn, capacity=3)
    service.buy_pass(conn, member, "class_pack", now=NOW)

    result = run_command(conn, BookCommand(member, session_id), now=NOW)

    assert result["status"] == "confirmed"
    entries = repository.list_audit_entries(conn)
    assert len(entries) == 1
    assert entries[0]["action"] == "book"
    assert entries[0]["member_id"] == member
    assert entries[0]["session_id"] == session_id
    assert f"booking_id={result['booking_id']}" in entries[0]["details"]


def test_book_command_on_full_session_logs_a_waitlist_join(conn):
    owner = make_member(conn, "a@example.com")
    waiting = make_member(conn, "b@example.com")
    session_id = make_session(conn, capacity=1)
    service.buy_pass(conn, owner, "drop_in", now=NOW)
    run_command(conn, BookCommand(owner, session_id), now=NOW)

    result = run_command(conn, BookCommand(waiting, session_id), now=NOW)

    assert result == {"status": "waitlisted", "position": 1}
    last = repository.list_audit_entries(conn)[-1]
    assert last["action"] == "waitlist_join"
    assert last["details"] == "position=1"


def test_cancel_command_logs_cancel_then_promotion_in_order(conn):
    owner = make_member(conn, "a@example.com")
    waiting = make_member(conn, "b@example.com")
    session_id = make_session(conn, capacity=1)
    service.buy_pass(conn, owner, "drop_in", now=NOW)
    service.buy_pass(conn, waiting, "class_pack", now=NOW)
    booked = run_command(conn, BookCommand(owner, session_id), now=NOW)
    run_command(conn, BookCommand(waiting, session_id), now=NOW)

    result = run_command(conn, CancelCommand(owner, booked["booking_id"]), now=NOW)

    assert result["promoted"]["member_id"] == waiting
    entries = repository.list_audit_entries(conn)
    assert [e["action"] for e in entries] == ["book", "waitlist_join", "cancel", "promote"]
    assert entries[2]["member_id"] == owner
    assert entries[3]["member_id"] == waiting


def test_cancel_with_nobody_waiting_logs_only_the_cancel(conn):
    member = make_member(conn, "a@example.com")
    session_id = make_session(conn, capacity=3)
    service.buy_pass(conn, member, "class_pack", now=NOW)
    booked = run_command(conn, BookCommand(member, session_id), now=NOW)

    result = run_command(conn, CancelCommand(member, booked["booking_id"]), now=NOW)

    assert result["promoted"] is None
    assert actions(conn) == ["book", "cancel"]


def test_failed_command_writes_no_audit_entry(conn):
    member = make_member(conn, "a@example.com")
    with pytest.raises(BookingError):
        run_command(conn, CancelCommand(member, 999), now=NOW)  # no such booking
    with pytest.raises(BookingError):
        run_command(conn, BookCommand(member, 999), now=NOW)    # no such session
    assert actions(conn) == []


def test_executing_a_command_directly_does_not_log(conn):
    # The command only describes and performs the action; run_command does the logging
    member = make_member(conn, "a@example.com")
    session_id = make_session(conn, capacity=3)
    service.buy_pass(conn, member, "class_pack", now=NOW)

    BookCommand(member, session_id).execute(conn, NOW, None)

    assert actions(conn) == []


def test_audit_entries_can_be_filtered_by_member(conn):
    a = make_member(conn, "a@example.com")
    b = make_member(conn, "b@example.com")
    session_id = make_session(conn, capacity=3)
    service.buy_pass(conn, a, "class_pack", now=NOW)
    service.buy_pass(conn, b, "class_pack", now=NOW)
    run_command(conn, BookCommand(a, session_id), now=NOW)
    run_command(conn, BookCommand(b, session_id), now=NOW)

    only_a = repository.list_audit_entries(conn, member_id=a)

    assert len(only_a) == 1
    assert only_a[0]["member_id"] == a


def test_bus_publish_returns_what_handlers_returned(conn):
    bus = events.EventBus()
    bus.subscribe(events.BookingCancelled, lambda e, c, n: "first")
    bus.subscribe(events.BookingCancelled, lambda e, c, n: "second")
    event = events.BookingCancelled(booking_id=1, member_id=2, session_id=3)
    assert bus.publish(event, conn, NOW) == ["first", "second"]