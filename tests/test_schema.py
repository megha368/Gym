import sqlite3

import pytest

from database.database import (
    get_connection,
    create_scheduling_tables,
    create_booking_tables,
)


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    create_scheduling_tables(c)
    create_booking_tables(c)
    yield c
    c.close()


def add_member_and_pass(conn, email="maya@example.com"):
    member_id = conn.execute(
        "INSERT INTO members (name, email, password_hash) VALUES (?, ?, ?)",
        ("Maya", email, "hash"),
    ).lastrowid
    pass_id = conn.execute(
        "INSERT INTO passes (member_id, type, remaining_uses) VALUES (?, 'class_pack', 10)",
        (member_id,),
    ).lastrowid
    return member_id, pass_id


def book(conn, member_id, session_id, pass_id):
    conn.execute(
        "INSERT INTO bookings (member_id, session_id, pass_id) VALUES (?, ?, ?)",
        (member_id, session_id, pass_id),
    )


def test_duplicate_email_rejected(conn):
    add_member_and_pass(conn)
    with pytest.raises(sqlite3.IntegrityError):
        add_member_and_pass(conn)


def test_booking_stores_session_id_without_a_sessions_row(conn):
    # Bookings is not tied to the sessions table
    member_id, pass_id = add_member_and_pass(conn)
    book(conn, member_id, 999, pass_id)  # no session 999 exists
    assert conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] == 1


def test_only_one_confirmed_booking_per_member_and_session(conn):
    member_id, pass_id = add_member_and_pass(conn)
    book(conn, member_id, 1, pass_id)
    with pytest.raises(sqlite3.IntegrityError):
        book(conn, member_id, 1, pass_id)


def test_can_rebook_after_cancelling(conn):
    member_id, pass_id = add_member_and_pass(conn)
    book(conn, member_id, 1, pass_id)
    conn.execute("UPDATE bookings SET status = 'cancelled'")
    book(conn, member_id, 1, pass_id)  # allowed: the old row is cancelled