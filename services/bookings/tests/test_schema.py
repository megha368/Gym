"""The database rules in Bookings' 001_init.sql, tested directly with SQL."""

import pytest

from database.database import IntegrityError


def add_member_and_pass(conn, email="maya@example.com"):
    member_id = conn.execute(
        "INSERT INTO members (name, email, password_hash) OUTPUT INSERTED.id VALUES (%s, %s, %s)",
        ("Maya", email, "hash"),
    ).fetchone()["id"]
    pass_id = conn.execute(
        "INSERT INTO passes (member_id, type, remaining_uses) OUTPUT INSERTED.id "
        "VALUES (%s, 'class_pack', 10)",
        (member_id,),
    ).fetchone()["id"]
    return member_id, pass_id


def book(conn, member_id, session_id, pass_id):
    conn.execute(
        "INSERT INTO bookings (member_id, session_id, pass_id) VALUES (%s, %s, %s)",
        (member_id, session_id, pass_id),
    )


def test_duplicate_email_rejected(conn):
    add_member_and_pass(conn)
    with pytest.raises(IntegrityError):
        add_member_and_pass(conn)


def test_booking_stores_session_id_without_a_sessions_row(conn):
    # session_id points at Scheduling's database, so nothing here checks it exists
    member_id, pass_id = add_member_and_pass(conn)
    book(conn, member_id, 999, pass_id)  # no session 999 exists anywhere
    assert conn.execute("SELECT COUNT(*) AS n FROM bookings").fetchone()["n"] == 1


def test_only_one_confirmed_booking_per_member_and_session(conn):
    member_id, pass_id = add_member_and_pass(conn)
    book(conn, member_id, 1, pass_id)
    with pytest.raises(IntegrityError):
        book(conn, member_id, 1, pass_id)


def test_can_rebook_after_cancelling(conn):
    member_id, pass_id = add_member_and_pass(conn)
    book(conn, member_id, 1, pass_id)
    conn.execute("UPDATE bookings SET status = 'cancelled'")
    book(conn, member_id, 1, pass_id)  # allowed: the old row is cancelled
    assert conn.execute("SELECT COUNT(*) AS n FROM bookings").fetchone()["n"] == 2


def test_pass_type_must_be_known(conn):
    member_id, _ = add_member_and_pass(conn)
    with pytest.raises(IntegrityError):
        conn.execute(
            "INSERT INTO passes (member_id, type) VALUES (%s, 'free_forever')", (member_id,)
        )
