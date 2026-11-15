from datetime import datetime

import pytest

from database.database import get_connection, create_scheduling_tables
from scheduling import service
from scheduling.service import SchedulingError

NOW = datetime(2026, 10, 7, 12, 0)


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    create_scheduling_tables(c)
    yield c
    c.close()


@pytest.fixture
def ids(conn):
    return {
        "class_type": service.create_class_type(conn, "Yoga"),
        "instructor": service.create_instructor(conn, "Sarah"),
    }


def make_session(conn, ids, start="2026-10-08T18:00", capacity=10):
    return service.create_session(
        conn, ids["class_type"], ids["instructor"], start, capacity
    )


def test_create_session_succeeds(conn, ids):
    session_id = make_session(conn, ids)
    assert service.get_session_info(conn, session_id)["capacity"] == 10


def test_duplicate_class_type_rejected(conn, ids):
    with pytest.raises(SchedulingError):
        service.create_class_type(conn, "Yoga")


def test_blank_names_rejected(conn):
    with pytest.raises(SchedulingError):
        service.create_class_type(conn, "   ")
    with pytest.raises(SchedulingError):
        service.create_instructor(conn, "")


@pytest.mark.parametrize("capacity", [0, -3, "ten"])
def test_invalid_capacity_rejected(conn, ids, capacity):
    with pytest.raises(SchedulingError):
        make_session(conn, ids, capacity=capacity)


def test_unknown_class_type_or_instructor_rejected(conn, ids):
    with pytest.raises(SchedulingError):
        service.create_session(conn, 999, ids["instructor"], "2026-10-08T18:00", 5)
    with pytest.raises(SchedulingError):
        service.create_session(conn, ids["class_type"], 999, "2026-10-08T18:00", 5)


def test_bad_start_time_rejected(conn, ids):
    with pytest.raises(SchedulingError):
        make_session(conn, ids, start="next tuesday")


def test_upcoming_excludes_past_and_cancelled_and_is_sorted(conn, ids):
    later = make_session(conn, ids, start="2026-10-09T18:00")
    sooner = make_session(conn, ids, start="2026-10-08T18:00")
    make_session(conn, ids, start="2026-10-01T18:00")  # in the past
    cancelled = make_session(conn, ids, start="2026-10-10T18:00")
    service.cancel_session(conn, cancelled)

    result = service.list_upcoming_sessions(conn, now=NOW)

    assert [s["id"] for s in result] == [sooner, later]


def test_cancel_session_sets_status(conn, ids):
    session_id = make_session(conn, ids)
    service.cancel_session(conn, session_id)
    assert service.get_session_info(conn, session_id)["status"] == "cancelled"


def test_cancel_twice_rejected(conn, ids):
    session_id = make_session(conn, ids)
    service.cancel_session(conn, session_id)
    with pytest.raises(SchedulingError):
        service.cancel_session(conn, session_id)


def test_unknown_session_rejected(conn):
    with pytest.raises(SchedulingError):
        service.get_session_info(conn, 999)


def test_is_open_for_booking(conn, ids):
    future = make_session(conn, ids, start="2026-10-08T18:00")
    past = make_session(conn, ids, start="2026-10-01T18:00")
    cancelled = make_session(conn, ids, start="2026-10-09T18:00")
    service.cancel_session(conn, cancelled)

    assert service.is_open_for_booking(conn, future, now=NOW) is True
    assert service.is_open_for_booking(conn, past, now=NOW) is False
    assert service.is_open_for_booking(conn, cancelled, now=NOW) is False


def test_get_session_details_includes_names(conn, ids):
    session_id = make_session(conn, ids)
    details = service.get_session_details(conn, session_id)
    assert details["class_name"] == "Yoga"
    assert details["instructor_name"] == "Sarah"
    assert details["capacity"] == 10


def test_get_session_details_unknown_session_rejected(conn):
    with pytest.raises(SchedulingError):
        service.get_session_details(conn, 999)