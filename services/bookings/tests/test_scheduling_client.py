"""The real client for the Scheduling service, with `requests` replaced by fakes, so we can
check how it handles each kind of answer without a Scheduling service running."""

from datetime import datetime

import pytest
import requests

from bookings import scheduling_client
from bookings.scheduling_client import SchedulingUnavailable, SessionNotFound


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


@pytest.fixture
def calls(monkeypatch):
    """Records what the client asked for; set calls.answer to choose what 'Scheduling' says."""
    class Calls(list):
        answer = FakeResponse(200, {})

    recorded = Calls()

    def fake_get(url, params=None, timeout=None):
        recorded.append({"url": url, "params": params, "timeout": timeout})
        if isinstance(recorded.answer, Exception):
            raise recorded.answer
        return recorded.answer

    monkeypatch.setattr(scheduling_client.requests, "get", fake_get)
    # the conftest stub replaces get_session; put the real one back for these tests
    monkeypatch.setattr(scheduling_client, "get_session", REAL_GET_SESSION)
    return recorded


REAL_GET_SESSION = scheduling_client.get_session


def test_get_session_calls_the_right_url_with_a_timeout(calls):
    calls.answer = FakeResponse(200, {"id": 7, "class_name": "Spin"})
    assert scheduling_client.get_session(7) == {"id": 7, "class_name": "Spin"}
    assert calls[0]["url"].endswith("/sessions/7")
    assert calls[0]["timeout"] == scheduling_client.SCHEDULING_TIMEOUT_S


def test_404_means_session_not_found(calls):
    calls.answer = FakeResponse(404, {"error": "Session does not exist"})
    with pytest.raises(SessionNotFound):
        scheduling_client.get_session(7)


def test_500_means_scheduling_unavailable(calls):
    calls.answer = FakeResponse(500, {})
    with pytest.raises(SchedulingUnavailable):
        scheduling_client.get_session(7)


@pytest.mark.parametrize("error", [requests.Timeout("too slow"), requests.ConnectionError("refused")])
def test_timeout_or_no_connection_means_scheduling_unavailable(calls, error):
    calls.answer = error
    with pytest.raises(SchedulingUnavailable):
        scheduling_client.get_session(7)


def test_is_open_for_booking():
    now = datetime(2026, 11, 18, 12, 0)
    assert scheduling_client.is_open_for_booking({"status": "scheduled", "start_time": "2026-11-18T18:00:00"}, now)
    assert not scheduling_client.is_open_for_booking({"status": "scheduled", "start_time": "2026-11-18T08:00:00"}, now)
    assert not scheduling_client.is_open_for_booking({"status": "cancelled", "start_time": "2026-11-18T18:00:00"}, now)
