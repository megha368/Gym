"""Scheduling's HTTP API and demo data, called through Flask's test client."""

from datetime import datetime

import pytest

from app import create_app
from database.seed import seed_demo_data
from scheduling import service

UI = "http://localhost:8080"  # the UI_ORIGIN default


@pytest.fixture
def client(conn):  # `conn` empties the database first
    app = create_app(seed_demo=False)
    app.config["TESTING"] = True
    return app.test_client()


def make_session(conn, start="2099-01-01T18:00", capacity=8):
    class_type = service.create_class_type(conn, f"Spin {start}")
    instructor = service.create_instructor(conn, "Diego")
    return service.create_session(conn, class_type, instructor, start, capacity)


def test_health_reports_ok_and_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "db": "ok", "version": "dev"}


def test_get_session_returns_details_with_names(client, conn):
    session_id = make_session(conn)
    body = client.get(f"/sessions/{session_id}").get_json()
    assert body["class_name"] == "Spin 2099-01-01T18:00"
    assert body["instructor_name"] == "Diego"
    assert body["capacity"] == 8
    assert body["status"] == "scheduled"


def test_unknown_session_is_404(client):
    response = client.get("/sessions/999999")
    assert response.status_code == 404
    assert "error" in response.get_json()


def test_list_sessions_only_shows_upcoming(client, conn):
    past = make_session(conn, start="2020-01-01T18:00")
    future = make_session(conn, start="2099-01-01T18:00")
    ids = [s["id"] for s in client.get("/sessions").get_json()]
    assert future in ids
    assert past not in ids


def test_list_sessions_from_a_given_time(client, conn):
    session_id = make_session(conn, start="2030-05-01T10:00")
    assert [s["id"] for s in client.get("/sessions?from=2030-05-01T09:00").get_json()] == [session_id]
    assert client.get("/sessions?from=2030-05-01T11:00").get_json() == []


def test_bad_from_parameter_is_400(client):
    assert client.get("/sessions?from=next-tuesday").status_code == 400


def test_cors_allows_only_the_ui(client):
    allowed = client.get("/sessions", headers={"Origin": UI})
    refused = client.get("/sessions", headers={"Origin": "https://evil.example"})
    assert allowed.headers["Access-Control-Allow-Origin"] == UI
    assert "Access-Control-Allow-Origin" not in refused.headers


def test_seed_fills_an_empty_database_with_a_week(conn):
    now = datetime(2026, 10, 7, 12, 0)
    assert seed_demo_data(conn, now=now) == 35  # 5 sessions a day for 7 days
    assert seed_demo_data(conn, now=now) == 0   # same day again: nothing added
    assert conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()["n"] == 35
    assert conn.execute("SELECT COUNT(*) AS n FROM class_types").fetchone()["n"] == 5


def test_seed_tops_up_new_days_later(conn):
    seed_demo_data(conn, now=datetime(2026, 10, 7, 12, 0))
    # three days later, the three new days at the end of the week get their sessions
    assert seed_demo_data(conn, now=datetime(2026, 10, 10, 12, 0)) == 15
    assert conn.execute("SELECT COUNT(*) AS n FROM class_types").fetchone()["n"] == 5  # no duplicates
