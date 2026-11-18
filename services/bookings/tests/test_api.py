"""Bookings' HTTP API, called through Flask's test client (no real server or browser)."""

import pytest

from app import create_app
from tests import scheduling_stub

UI = "http://localhost:8080"  # the UI_ORIGIN default


@pytest.fixture
def client(conn):  # `conn` empties the database first
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def register(client, email="maya@example.com", password="secret123"):
    response = client.post("/auth/register", json={"name": "Maya", "email": email, "password": password})
    assert response.status_code == 201, response.get_json()
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def future_session(capacity=5):
    return scheduling_stub.add_session("2099-01-01T18:00", capacity, class_name="Spin")


# ---------- health and errors ----------

def test_health_reports_ok_and_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "db": "ok", "version": "dev"}


def test_unknown_url_answers_json_404(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert "error" in response.get_json()


# ---------- login tokens ----------

def test_register_returns_a_token_that_works(client):
    headers = register(client)
    response = client.get("/me", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["member"]["email"] == "maya@example.com"


def test_login_with_wrong_password_is_rejected(client):
    register(client)
    response = client.post("/auth/login", json={"email": "maya@example.com", "password": "wrong-one"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid email or password"}


def test_login_returns_a_new_token(client):
    register(client)
    response = client.post("/auth/login", json={"email": "maya@example.com", "password": "secret123"})
    assert response.status_code == 200
    assert response.get_json()["token"]


def test_endpoints_need_a_token(client):
    assert client.get("/bookings").status_code == 401
    assert client.get("/passes").status_code == 401


def test_forged_token_is_rejected(client):
    assert client.get("/me", headers={"Authorization": "Bearer made.up.token"}).status_code == 401


def test_duplicate_email_is_rejected(client):
    register(client)
    response = client.post("/auth/register", json={"name": "X", "email": "maya@example.com", "password": "secret123"})
    assert response.status_code == 400


# ---------- CORS ----------

def test_cors_allows_the_ui_origin(client):
    response = client.options("/bookings", headers={"Origin": UI, "Access-Control-Request-Method": "POST"})
    assert response.headers["Access-Control-Allow-Origin"] == UI
    assert "Authorization" in response.headers["Access-Control-Allow-Headers"]


def test_cors_refuses_other_websites(client):
    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in response.headers


# ---------- passes, booking, cancelling ----------

def test_booking_without_a_pass_is_rejected(client):
    headers = register(client)
    response = client.post("/bookings", json={"session_id": future_session()}, headers=headers)
    assert response.status_code == 400
    assert "pass" in response.get_json()["error"]


def test_buy_pass_book_and_see_it_in_my_bookings(client):
    headers = register(client)
    session_id = future_session()
    assert client.post("/passes", json={"pass_type": "class_pack"}, headers=headers).status_code == 201

    booked = client.post("/bookings", json={"session_id": session_id}, headers=headers)
    assert booked.status_code == 201
    assert booked.get_json()["status"] == "confirmed"

    mine = client.get("/bookings", headers=headers).get_json()
    assert mine["details_missing"] is False
    assert mine["bookings"][0]["class_name"] == "Spin"  # detail that came from Scheduling
    assert client.get("/passes", headers=headers).get_json()["passes"][0]["remaining_uses"] == 9


def test_full_class_waitlists_then_cancel_promotes(client):
    owner = register(client, "owner@example.com")
    waiting = register(client, "waiting@example.com")
    session_id = future_session(capacity=1)
    for headers in (owner, waiting):
        client.post("/passes", json={"pass_type": "class_pack"}, headers=headers)

    booking_id = client.post("/bookings", json={"session_id": session_id}, headers=owner).get_json()["booking_id"]
    joined = client.post("/bookings", json={"session_id": session_id}, headers=waiting).get_json()
    assert joined == {"status": "waitlisted", "position": 1}

    cancelled = client.post(f"/bookings/{booking_id}/cancel", headers=owner)
    assert cancelled.get_json() == {"booking_id": booking_id, "promoted": True}
    assert client.get("/bookings", headers=waiting).get_json()["bookings"][0]["session_id"] == session_id


def test_cannot_cancel_someone_elses_booking(client):
    owner = register(client, "owner@example.com")
    other = register(client, "other@example.com")
    client.post("/passes", json={"pass_type": "class_pack"}, headers=owner)
    booking_id = client.post("/bookings", json={"session_id": future_session()}, headers=owner).get_json()["booking_id"]

    assert client.post(f"/bookings/{booking_id}/cancel", headers=other).status_code == 400


def test_leave_waitlist(client):
    owner = register(client, "owner@example.com")
    waiting = register(client, "waiting@example.com")
    session_id = future_session(capacity=1)
    for headers in (owner, waiting):
        client.post("/passes", json={"pass_type": "class_pack"}, headers=headers)
    client.post("/bookings", json={"session_id": session_id}, headers=owner)
    client.post("/bookings", json={"session_id": session_id}, headers=waiting)

    assert client.delete(f"/waitlist/{session_id}", headers=waiting).status_code == 200
    assert client.get("/bookings", headers=waiting).get_json()["waitlist"] == []


def test_booking_needs_a_numeric_session_id(client):
    headers = register(client)
    assert client.post("/bookings", json={"session_id": "abc"}, headers=headers).status_code == 400


# ---------- availability ----------

def test_availability_without_login(client):
    session_id = future_session()
    response = client.get(f"/availability?session_ids={session_id}")
    assert response.get_json() == {
        "sessions": {str(session_id): {"booked": 0, "member_status": None, "waitlist_position": None}}
    }


def test_availability_rejects_bad_ids(client):
    assert client.get("/availability?session_ids=1,x").status_code == 400


# ---------- partial failure ----------

def test_booking_answers_503_when_scheduling_is_down(client):
    headers = register(client)
    client.post("/passes", json={"pass_type": "class_pack"}, headers=headers)
    session_id = future_session()
    scheduling_stub.down = True

    response = client.post("/bookings", json={"session_id": session_id}, headers=headers)

    assert response.status_code == 503
    assert "temporarily unavailable" in response.get_json()["error"]


def test_own_data_still_works_when_scheduling_is_down(client):
    headers = register(client)
    client.post("/passes", json={"pass_type": "class_pack"}, headers=headers)
    client.post("/bookings", json={"session_id": future_session()}, headers=headers)
    scheduling_stub.down = True

    assert client.get("/passes", headers=headers).status_code == 200
    mine = client.get("/bookings", headers=headers).get_json()
    assert mine["details_missing"] is True
    assert len(mine["bookings"]) == 1
