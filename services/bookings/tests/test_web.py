from datetime import datetime, timedelta

import pytest

from database.database import (
    get_connection,
    create_scheduling_tables,
)
from database.seed import seed_demo_data
from scheduling import service as scheduling_service
from web import create_app


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def app(db_path):
    app = create_app(db_path=db_path, seed_demo=False)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def session_id(db_path):
    """One 1-spot class tomorrow, created through Scheduling's service."""
    conn = get_connection(db_path)
    class_type = scheduling_service.create_class_type(conn, "Pilates")
    instructor = scheduling_service.create_instructor(conn, "Diego")
    start = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat()
    new_id = scheduling_service.create_session(conn, class_type, instructor, start, 1)
    conn.close()
    return new_id


def register(client, name="Maya", email="maya@example.com", password="secret123"):
    return client.post(
        "/register",
        data={"name": name, "email": email, "password": password},
        follow_redirects=True,
    )


def buy(client, pass_type="class_pack"):
    return client.post("/passes", data={"pass_type": pass_type}, follow_redirects=True)


def test_health(client):
    assert client.get("/health").get_json() == {"status": "ok"}


def test_schedule_is_public_and_shows_sessions(client, session_id):
    response = client.get("/schedule")
    assert response.status_code == 200
    assert b"Pilates" in response.data
    assert b"Log in to book" in response.data


def test_register_logs_the_member_in(client):
    response = register(client)
    assert b"Log out" in response.data


def test_register_duplicate_email_shows_error(client):
    register(client)
    client.post("/logout")
    response = register(client)
    assert b"already exists" in response.data


def test_login_with_wrong_password_is_rejected(client):
    register(client)
    client.post("/logout")
    response = client.post(
        "/login",
        data={"email": "maya@example.com", "password": "nope-nope"},
        follow_redirects=True,
    )
    assert b"Invalid email or password" in response.data
    assert b"Log out" not in response.data


def test_login_works_after_logout(client):
    register(client)
    client.post("/logout")
    response = client.post(
        "/login",
        data={"email": "maya@example.com", "password": "secret123"},
        follow_redirects=True,
    )
    assert b"Log out" in response.data


def test_logout_ends_the_session(client):
    register(client)
    client.post("/logout")
    assert client.get("/bookings").status_code == 302


def test_booking_and_bookings_page_require_login(client, session_id):
    response = client.post(f"/book/{session_id}")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert client.get("/bookings").status_code == 302


def test_booking_without_a_pass_shows_error(client, session_id):
    register(client)
    response = client.post(f"/book/{session_id}", follow_redirects=True)
    assert b"no valid pass" in response.data


def test_buy_pass_then_book_then_see_it_in_my_bookings(client, session_id):
    register(client)
    buy(client)
    response = client.post(f"/book/{session_id}", follow_redirects=True)
    assert b"Booked! See you there" in response.data

    page = client.get("/bookings")
    assert b"Pilates" in page.data
    assert b"9 left" in page.data  # class pack of 10, one used


def test_full_class_waitlists_then_cancel_promotes(app, db_path, session_id):
    owner = app.test_client()
    waiting = app.test_client()
    register(owner, "Owen", "owen@example.com")
    buy(owner, "drop_in")
    register(waiting, "Wendy", "wendy@example.com")
    buy(waiting)
    owner.post(f"/book/{session_id}")

    response = waiting.post(f"/book/{session_id}", follow_redirects=True)
    assert b"#1 on the waitlist" in response.data

    conn = get_connection(db_path)
    booking_id = conn.execute("SELECT id FROM bookings").fetchone()["id"]
    conn.close()
    owner.post(f"/bookings/{booking_id}/cancel", follow_redirects=True)

    page = waiting.get("/bookings")
    assert b"Pilates" in page.data
    assert b"On the waitlist" not in page.data  # Wendy was promoted


def test_cannot_cancel_someone_elses_booking(app, db_path, session_id):
    owner = app.test_client()
    other = app.test_client()
    register(owner, "Owen", "owen@example.com")
    buy(owner)
    register(other, "Olive", "olive@example.com")
    owner.post(f"/book/{session_id}")

    conn = get_connection(db_path)
    booking_id = conn.execute("SELECT id FROM bookings").fetchone()["id"]
    conn.close()
    response = other.post(f"/bookings/{booking_id}/cancel", follow_redirects=True)

    assert b"Booking not found" in response.data


def test_seed_fills_an_empty_database_only_once():
    conn = get_connection(":memory:")
    create_scheduling_tables(conn)
    now = datetime(2026, 10, 7, 12, 0)

    assert seed_demo_data(conn, now=now) is True
    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 35
    assert seed_demo_data(conn, now=now) is False
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == count