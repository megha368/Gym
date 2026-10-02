from dataclasses import dataclass
from datetime import datetime

import pytest

from database.database import (
    get_connection,
    create_scheduling_tables,
    create_booking_tables,
)
from bookings import auth, events, repository, service
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


def make_session(conn, start="2026-10-08T18:00", capacity=1):
    class_type = scheduling_service.create_class_type(conn, f"Yoga {start}")
    instructor = scheduling_service.create_instructor(conn, "Sarah")
    return scheduling_service.create_session(conn, class_type, instructor, start, capacity)


def full_session(conn):
    """A capacity-1 session already booked by 'owner'."""
    owner = make_member(conn, "owner@example.com")
    session_id = make_session(conn)
    service.buy_pass(conn, owner, "drop_in", now=NOW)
    booking_id = service.book_class(conn, owner, session_id, now=NOW)
    return owner, session_id, booking_id


def remaining(conn, pass_id):
    return repository.get_pass(conn, pass_id)["remaining_uses"]


# ---------- joining the waitlist ----------

def test_join_full_session_gives_positions_in_order(conn):
    _, session_id, _ = full_session(conn)
    second = make_member(conn, "b@example.com")
    third = make_member(conn, "c@example.com")

    assert service.join_waitlist(conn, second, session_id, now=NOW) == 1
    assert service.join_waitlist(conn, third, session_id, now=NOW) == 2


def test_cannot_join_waitlist_when_session_has_room(conn):
    member = make_member(conn, "a@example.com")
    session_id = make_session(conn, capacity=3)
    with pytest.raises(BookingError):
        service.join_waitlist(conn, member, session_id, now=NOW)


def test_cannot_join_waitlist_twice(conn):
    _, session_id, _ = full_session(conn)
    member = make_member(conn, "b@example.com")
    service.join_waitlist(conn, member, session_id, now=NOW)
    with pytest.raises(BookingError):
        service.join_waitlist(conn, member, session_id, now=NOW)


def test_cannot_join_waitlist_for_session_you_already_booked(conn):
    owner, session_id, _ = full_session(conn)
    with pytest.raises(BookingError):
        service.join_waitlist(conn, owner, session_id, now=NOW)


def test_join_waitlist_rejects_unknown_member_session_and_closed_session(conn):
    owner, session_id, _ = full_session(conn)
    member = make_member(conn, "b@example.com")
    with pytest.raises(BookingError):
        service.join_waitlist(conn, 999, session_id, now=NOW)
    with pytest.raises(BookingError):
        service.join_waitlist(conn, member, 999, now=NOW)
    scheduling_service.cancel_session(conn, session_id)
    with pytest.raises(BookingError):
        service.join_waitlist(conn, member, session_id, now=NOW)


# ---------- leaving the waitlist ----------

def test_leaving_moves_everyone_behind_up(conn):
    _, session_id, _ = full_session(conn)
    second = make_member(conn, "b@example.com")
    third = make_member(conn, "c@example.com")
    service.join_waitlist(conn, second, session_id, now=NOW)
    service.join_waitlist(conn, third, session_id, now=NOW)

    service.leave_waitlist(conn, second, session_id)

    assert service.get_waitlist_position(conn, second, session_id) is None
    assert service.get_waitlist_position(conn, third, session_id) == 1


def test_leave_when_not_on_waitlist_rejected(conn):
    _, session_id, _ = full_session(conn)
    member = make_member(conn, "b@example.com")
    with pytest.raises(BookingError):
        service.leave_waitlist(conn, member, session_id)


# ---------- book_or_join_waitlist ----------

def test_book_or_join_confirms_when_room_then_waitlists_when_full(conn):
    first = make_member(conn, "a@example.com")
    second = make_member(conn, "b@example.com")
    session_id = make_session(conn, capacity=1)
    service.buy_pass(conn, first, "class_pack", now=NOW)

    result_first = service.book_or_join_waitlist(conn, first, session_id, now=NOW)
    result_second = service.book_or_join_waitlist(conn, second, session_id, now=NOW)

    assert result_first["status"] == "confirmed"
    assert result_second == {"status": "waitlisted", "position": 1}


# ---------- cancellation ----------

def test_cancel_marks_booking_cancelled_and_frees_the_spot(conn):
    owner, session_id, booking_id = full_session(conn)

    result = service.cancel_booking(conn, owner, booking_id, now=NOW)

    assert result["session_id"] == session_id
    assert repository.get_booking(conn, booking_id)["status"] == "cancelled"
    assert repository.count_confirmed_bookings(conn, session_id) == 0


def test_cancel_refunds_a_class_pack_credit(conn):
    member = make_member(conn, "a@example.com")
    session_id = make_session(conn, capacity=3)
    pass_id = service.buy_pass(conn, member, "class_pack", now=NOW)
    booking_id = service.book_class(conn, member, session_id, now=NOW)
    assert remaining(conn, pass_id) == 9

    service.cancel_booking(conn, member, booking_id, now=NOW)

    assert remaining(conn, pass_id) == 10


def test_cancel_makes_a_used_drop_in_valid_again(conn):
    member = make_member(conn, "a@example.com")
    session_id = make_session(conn, capacity=3)
    pass_id = service.buy_pass(conn, member, "drop_in", now=NOW)
    booking_id = service.book_class(conn, member, session_id, now=NOW)
    assert service.find_usable_pass(conn, member, NOW) is None

    service.cancel_booking(conn, member, booking_id, now=NOW)

    assert remaining(conn, pass_id) == 1
    assert service.find_usable_pass(conn, member, NOW)["id"] == pass_id


def test_cancel_membership_booking_leaves_pass_unchanged(conn):
    member = make_member(conn, "a@example.com")
    session_id = make_session(conn, capacity=3)
    pass_id = service.buy_pass(conn, member, "membership", now=NOW)
    booking_id = service.book_class(conn, member, session_id, now=NOW)

    service.cancel_booking(conn, member, booking_id, now=NOW)

    assert remaining(conn, pass_id) is None


def test_can_rebook_after_cancelling(conn):
    member = make_member(conn, "a@example.com")
    session_id = make_session(conn, capacity=3)
    service.buy_pass(conn, member, "class_pack", now=NOW)
    booking_id = service.book_class(conn, member, session_id, now=NOW)
    service.cancel_booking(conn, member, booking_id, now=NOW)

    assert service.book_class(conn, member, session_id, now=NOW) is not None


def test_cannot_cancel_someone_elses_or_unknown_booking(conn):
    _, _, booking_id = full_session(conn)
    stranger = make_member(conn, "b@example.com")
    with pytest.raises(BookingError):
        service.cancel_booking(conn, stranger, booking_id, now=NOW)
    with pytest.raises(BookingError):
        service.cancel_booking(conn, stranger, 999, now=NOW)


def test_cannot_cancel_twice(conn):
    owner, _, booking_id = full_session(conn)
    service.cancel_booking(conn, owner, booking_id, now=NOW)
    with pytest.raises(BookingError):
        service.cancel_booking(conn, owner, booking_id, now=NOW)


def test_cannot_cancel_after_session_started(conn):
    owner, _, booking_id = full_session(conn)  # session starts 2026-10-08T18:00
    after_start = datetime(2026, 10, 8, 19, 0)
    with pytest.raises(BookingError):
        service.cancel_booking(conn, owner, booking_id, now=after_start)

# ---------- waitlist promotion (Observer) ----------

def test_cancel_promotes_first_waitlisted_member(conn):
    owner, session_id, booking_id = full_session(conn)
    second = make_member(conn, "b@example.com")
    third = make_member(conn, "c@example.com")
    second_pass = service.buy_pass(conn, second, "class_pack", now=NOW)
    service.buy_pass(conn, third, "class_pack", now=NOW)
    service.join_waitlist(conn, second, session_id, now=NOW)
    service.join_waitlist(conn, third, session_id, now=NOW)

    service.cancel_booking(conn, owner, booking_id, now=NOW)

    assert repository.get_confirmed_booking(conn, second, session_id) is not None
    assert repository.get_confirmed_booking(conn, third, session_id) is None
    assert repository.count_confirmed_bookings(conn, session_id) == 1
    assert remaining(conn, second_pass) == 9  # promotion charged the pass
    assert service.get_waitlist_position(conn, second, session_id) is None
    assert service.get_waitlist_position(conn, third, session_id) == 1


def test_promotion_skips_member_without_a_valid_pass(conn):
    owner, session_id, booking_id = full_session(conn)
    no_pass = make_member(conn, "b@example.com")
    has_pass = make_member(conn, "c@example.com")
    service.buy_pass(conn, has_pass, "class_pack", now=NOW)
    service.join_waitlist(conn, no_pass, session_id, now=NOW)
    service.join_waitlist(conn, has_pass, session_id, now=NOW)

    service.cancel_booking(conn, owner, booking_id, now=NOW)

    assert repository.get_confirmed_booking(conn, no_pass, session_id) is None
    assert repository.get_confirmed_booking(conn, has_pass, session_id) is not None
    assert service.get_waitlist_position(conn, no_pass, session_id) is None


def test_spot_stays_free_when_nobody_waiting_can_be_promoted(conn):
    owner, session_id, booking_id = full_session(conn)
    no_pass = make_member(conn, "b@example.com")
    service.join_waitlist(conn, no_pass, session_id, now=NOW)

    service.cancel_booking(conn, owner, booking_id, now=NOW)

    assert repository.count_confirmed_bookings(conn, session_id) == 0
    assert service.get_waitlist_position(conn, no_pass, session_id) is None


def test_no_promotion_when_the_session_has_no_free_spot(conn):
    _, session_id, _ = full_session(conn)
    waiting = make_member(conn, "b@example.com")
    service.buy_pass(conn, waiting, "class_pack", now=NOW)
    service.join_waitlist(conn, waiting, session_id, now=NOW)

    assert service.promote_next_from_waitlist(conn, session_id, now=NOW) is None
    assert service.get_waitlist_position(conn, waiting, session_id) == 1
    assert repository.count_confirmed_bookings(conn, session_id) == 1


def test_no_promotion_into_a_session_the_studio_cancelled(conn):
    owner, session_id, booking_id = full_session(conn)
    waiting = make_member(conn, "b@example.com")
    service.buy_pass(conn, waiting, "class_pack", now=NOW)
    service.join_waitlist(conn, waiting, session_id, now=NOW)
    scheduling_service.cancel_session(conn, session_id)

    service.cancel_booking(conn, owner, booking_id, now=NOW)

    assert repository.get_confirmed_booking(conn, waiting, session_id) is None


def test_promotion_skips_member_who_already_has_a_booking(conn):
    session_id = make_session(conn, capacity=3)
    booked = make_member(conn, "a@example.com")
    waiting = make_member(conn, "b@example.com")
    service.buy_pass(conn, booked, "class_pack", now=NOW)
    service.buy_pass(conn, waiting, "class_pack", now=NOW)
    service.book_class(conn, booked, session_id, now=NOW)
    # Force a waitlist entry for the already-booked member, then one for 'waiting'
    repository.add_waitlist_entry(conn, booked, session_id)
    repository.add_waitlist_entry(conn, waiting, session_id)
    conn.commit()

    result = service.promote_next_from_waitlist(conn, session_id, now=NOW)

    assert result["member_id"] == waiting
    assert repository.count_confirmed_bookings(conn, session_id) == 2
    assert service.get_waitlist_position(conn, booked, session_id) is None


# ---------- the event bus itself ----------

@dataclass(frozen=True)
class SomethingElse:
    pass


def test_bus_calls_handler_with_event_connection_and_time(conn):
    bus = events.EventBus()
    received = []
    bus.subscribe(events.BookingCancelled, lambda e, c, n: received.append((e, c, n)))
    event = events.BookingCancelled(booking_id=1, member_id=2, session_id=3)

    bus.publish(event, conn, NOW)

    assert received == [(event, conn, NOW)]


def test_bus_only_calls_handlers_for_the_published_event_type(conn):
    bus = events.EventBus()
    received = []
    bus.subscribe(events.BookingCancelled, lambda e, c, n: received.append(e))

    bus.publish(SomethingElse(), conn, NOW)

    assert received == []


def test_cancel_booking_publishes_event_on_the_given_bus(conn):
    owner, session_id, booking_id = full_session(conn)
    bus = events.EventBus()
    seen = []
    bus.subscribe(events.BookingCancelled, lambda e, c, n: seen.append(e))

    service.cancel_booking(conn, owner, booking_id, now=NOW, bus=bus)

    assert seen == [
        events.BookingCancelled(booking_id=booking_id, member_id=owner, session_id=session_id)
    ]


def test_cancel_does_not_know_about_the_waitlist(conn):
    # With a bus that has no subscribers, cancelling frees the spot but promotes nobody
    owner, session_id, booking_id = full_session(conn)
    waiting = make_member(conn, "b@example.com")
    service.buy_pass(conn, waiting, "class_pack", now=NOW)
    service.join_waitlist(conn, waiting, session_id, now=NOW)

    service.cancel_booking(conn, owner, booking_id, now=NOW, bus=events.EventBus())

    assert repository.get_confirmed_booking(conn, waiting, session_id) is None
    assert service.get_waitlist_position(conn, waiting, session_id) == 1