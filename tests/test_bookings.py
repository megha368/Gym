from datetime import datetime

import pytest

from database.database import (
    get_connection,
    create_scheduling_tables,
    create_booking_tables,
)
from bookings import auth, repository, service, strategies
from bookings.service import BookingError, SessionFullError
from scheduling import service as scheduling_service

NOW = datetime(2026, 10, 7, 12, 0)


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    create_scheduling_tables(c)
    create_booking_tables(c)
    yield c
    c.close()


def make_member(conn, email="maya@example.com"):
    return auth.register(conn, "Maya", email, "secret123")


def make_session(conn, start="2026-10-08T18:00", capacity=5):
    class_type = scheduling_service.create_class_type(
        conn, f"Yoga {start} {capacity}"
    )
    instructor = scheduling_service.create_instructor(conn, "Sarah")
    return scheduling_service.create_session(conn, class_type, instructor, start, capacity)


def pass_row(conn, pass_id):
    return dict(repository.get_pass(conn, pass_id))


# ---------- strategies ----------

def test_drop_in_and_class_pack_countdown():
    p = {"remaining_uses": 3, "expires_at": None}
    s = strategies.get_strategy("class_pack")
    assert s.is_valid(p, NOW)
    assert s.remaining_after_use(p) == 2
    assert s.remaining_after_refund(p) == 4


def test_pass_with_no_uses_left_is_invalid():
    assert not strategies.get_strategy("drop_in").is_valid(
        {"remaining_uses": 0, "expires_at": None}, NOW
    )


def test_expired_pass_is_invalid():
    expired = {"remaining_uses": 5, "expires_at": "2026-10-01T00:00:00"}
    assert not strategies.get_strategy("class_pack").is_valid(expired, NOW)


def test_membership_is_unlimited_until_expiry():
    s = strategies.get_strategy("membership")
    active = {"remaining_uses": None, "expires_at": "2026-11-01T00:00:00"}
    expired = {"remaining_uses": None, "expires_at": "2026-10-01T00:00:00"}
    assert s.is_valid(active, NOW)
    assert s.remaining_after_use(active) is None
    assert s.remaining_after_refund(active) is None
    assert not s.is_valid(expired, NOW)


def test_unknown_strategy_rejected():
    with pytest.raises(ValueError):
        strategies.get_strategy("gold_card")


# ---------- buying passes ----------

@pytest.mark.parametrize("pass_type,uses,has_expiry", [
    ("drop_in", 1, False),
    ("class_pack", 10, True),
    ("membership", None, True),
])
def test_buy_pass_defaults(conn, pass_type, uses, has_expiry):
    member_id = make_member(conn)
    pass_id = service.buy_pass(conn, member_id, pass_type, now=NOW)
    row = pass_row(conn, pass_id)
    assert row["remaining_uses"] == uses
    assert (row["expires_at"] is not None) == has_expiry


def test_buy_pass_rejects_bad_input(conn):
    member_id = make_member(conn)
    with pytest.raises(BookingError):
        service.buy_pass(conn, member_id, "gold_card", now=NOW)
    with pytest.raises(BookingError):
        service.buy_pass(conn, 999, "drop_in", now=NOW)


# ---------- choosing a pass ----------

def test_membership_is_chosen_before_class_pack_before_drop_in(conn):
    member_id = make_member(conn)
    service.buy_pass(conn, member_id, "drop_in", now=NOW)
    service.buy_pass(conn, member_id, "class_pack", now=NOW)
    service.buy_pass(conn, member_id, "membership", now=NOW)
    assert service.find_usable_pass(conn, member_id, NOW)["type"] == "membership"


def test_find_usable_pass_skips_expired_and_returns_none_when_nothing_valid(conn):
    member_id = make_member(conn)
    assert service.find_usable_pass(conn, member_id, NOW) is None
    service.buy_pass(conn, member_id, "membership", now=datetime(2026, 1, 1))  # long expired
    assert service.find_usable_pass(conn, member_id, NOW) is None


# ---------- booking ----------

def test_book_class_creates_booking_and_uses_a_pass_credit(conn):
    member_id = make_member(conn)
    session_id = make_session(conn)
    pass_id = service.buy_pass(conn, member_id, "class_pack", now=NOW)

    booking_id = service.book_class(conn, member_id, session_id, now=NOW)

    assert booking_id is not None
    assert pass_row(conn, pass_id)["remaining_uses"] == 9
    assert repository.get_confirmed_booking(conn, member_id, session_id)["pass_id"] == pass_id


def test_membership_booking_does_not_change_the_pass(conn):
    member_id = make_member(conn)
    session_id = make_session(conn)
    pass_id = service.buy_pass(conn, member_id, "membership", now=NOW)
    service.book_class(conn, member_id, session_id, now=NOW)
    assert pass_row(conn, pass_id)["remaining_uses"] is None


def test_double_booking_rejected(conn):
    member_id = make_member(conn)
    session_id = make_session(conn)
    service.buy_pass(conn, member_id, "class_pack", now=NOW)
    service.book_class(conn, member_id, session_id, now=NOW)
    with pytest.raises(BookingError):
        service.book_class(conn, member_id, session_id, now=NOW)


def test_full_session_raises_and_does_not_charge_the_pass(conn):
    first = make_member(conn, "a@example.com")
    second = make_member(conn, "b@example.com")
    session_id = make_session(conn, capacity=1)
    service.buy_pass(conn, first, "drop_in", now=NOW)
    second_pass = service.buy_pass(conn, second, "class_pack", now=NOW)

    service.book_class(conn, first, session_id, now=NOW)
    with pytest.raises(SessionFullError):
        service.book_class(conn, second, session_id, now=NOW)

    assert pass_row(conn, second_pass)["remaining_uses"] == 10


def test_booking_without_a_valid_pass_rejected(conn):
    member_id = make_member(conn)
    session_id = make_session(conn)
    with pytest.raises(BookingError):
        service.book_class(conn, member_id, session_id, now=NOW)


def test_booking_unknown_member_or_session_rejected(conn):
    member_id = make_member(conn)
    session_id = make_session(conn)
    service.buy_pass(conn, member_id, "class_pack", now=NOW)
    with pytest.raises(BookingError):
        service.book_class(conn, 999, session_id, now=NOW)
    with pytest.raises(BookingError):
        service.book_class(conn, member_id, 999, now=NOW)


def test_cancelled_or_past_session_rejected(conn):
    member_id = make_member(conn)
    service.buy_pass(conn, member_id, "class_pack", now=NOW)
    cancelled = make_session(conn, start="2026-10-09T18:00")
    scheduling_service.cancel_session(conn, cancelled)
    past = make_session(conn, start="2026-10-01T18:00")
    with pytest.raises(BookingError):
        service.book_class(conn, member_id, cancelled, now=NOW)
    with pytest.raises(BookingError):
        service.book_class(conn, member_id, past, now=NOW)


def test_list_member_bookings_includes_session_details(conn):
    member_id = make_member(conn)
    session_id = make_session(conn, start="2026-10-08T18:00")
    service.buy_pass(conn, member_id, "class_pack", now=NOW)
    service.book_class(conn, member_id, session_id, now=NOW)

    bookings = service.list_member_bookings(conn, member_id)

    assert len(bookings) == 1
    assert bookings[0]["session_id"] == session_id
    assert bookings[0]["start_time"] == "2026-10-08T18:00:00"