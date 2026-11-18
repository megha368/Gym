"""Shared test setup: every test runs against a real SQL Server database.

TEST_DATABASE_URL must point at a database the tests are allowed to wipe, for example
    mssql://sa:<password>@localhost:1433/bookings_test
It is created if it doesn't exist, brought up to date with this service's migrations
once, and emptied before every test, so each test starts from a clean database.
"""

import os
from urllib.parse import urlparse

import pymssql
import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "Set TEST_DATABASE_URL to a SQL Server database the tests may wipe, e.g. "
        "mssql://sa:<password>@localhost:1433/bookings_test"
    )
# The code under test reads its settings from these when it is imported, below
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-only-secret")

from tests import scheduling_stub  # noqa: E402
from database.database import STARTUP_ATTEMPTS, _parse_database_url, get_connection  # noqa: E402
from database.migrations import apply_migrations  # noqa: E402

# Emptied before each test, in this order (rows that point at others go first)
TABLES = ["audit_log", "waitlist_entries", "bookings", "passes", "members"]


def _create_test_database():
    """CREATE DATABASE if it's missing (needs a login allowed to create databases, like sa)."""
    settings = _parse_database_url(TEST_DATABASE_URL)
    name = settings.pop("database")
    if not name.replace("_", "").isalnum():
        raise RuntimeError(f"Unexpected test database name: {name}")
    server = pymssql.connect(**settings, database="master", autocommit=True)
    try:
        server.cursor().execute(f"IF DB_ID('{name}') IS NULL CREATE DATABASE [{name}]")
    finally:
        server.close()


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Once per test run: make sure the test database exists and has the latest schema."""
    assert urlparse(TEST_DATABASE_URL).path.endswith("_test"), "refusing to wipe a non-test database"
    _create_test_database()
    conn = get_connection(attempts=STARTUP_ATTEMPTS)
    try:
        apply_migrations(conn)
    finally:
        conn.close()


@pytest.fixture
def conn():
    """A connection to an empty test database."""
    c = get_connection()
    for table in TABLES:
        c.execute(f"DELETE FROM {table}")
    c.commit()
    yield c
    c.rollback()
    c.close()


@pytest.fixture(autouse=True)
def stub_scheduling(monkeypatch):
    """Replace the Scheduling service with the stub in every test (see scheduling_stub.py)."""
    from bookings import scheduling_client

    scheduling_stub.reset()
    monkeypatch.setattr(scheduling_client, "get_session", scheduling_stub.get_session)
    monkeypatch.setattr(scheduling_client, "list_upcoming_sessions", scheduling_stub.list_upcoming_sessions)
    return scheduling_stub
