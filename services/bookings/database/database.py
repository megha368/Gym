"""Connecting to this service's own SQL Server database.

The connection string comes from the DATABASE_URL environment variable, in the form
    mssql://<user>:<password>@<host>:<port>/<database>
(URL-encode any special characters in the password).
"""

import time
from urllib.parse import unquote, urlparse

import pymssql

from config.settings import DATABASE_URL

# The rest of the code catches these instead of importing pymssql itself, so the
# database driver is only mentioned in this file.
IntegrityError = pymssql.IntegrityError  # a UNIQUE, CHECK or FOREIGN KEY rule was broken
DatabaseError = pymssql.Error            # any database error

# How hard to try before giving up on connecting. At startup we wait up to about a
# minute, because on Azure the serverless database may be paused and takes that long
# to resume (connections fail with error 40613 meanwhile). During a normal request we
# give up much sooner, so a user isn't left waiting for a minute.
STARTUP_ATTEMPTS = 8   # waits 1+2+4+8+10+10+10 s between attempts, about 45 s in total
REQUEST_ATTEMPTS = 3   # waits 1+2 s


class Connection:
    """A thin wrapper around a pymssql connection.

    It keeps the conn.execute(sql, params) style used in Assignment 1 with sqlite3, so the
    repository code reads the same. Rows come back as dictionaries (row["capacity"]).
    """

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=None):
        cursor = self._raw.cursor(as_dict=True)
        cursor.execute(sql, tuple(params) if params else None)
        return cursor

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


def _parse_database_url(url):
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    parts = urlparse(url)
    return {
        "server": parts.hostname,
        "port": parts.port or 1433,
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": parts.path.lstrip("/"),
    }


def get_connection(attempts=REQUEST_ATTEMPTS, url=None):
    """Open a connection, retrying with a growing pause (backoff) if the database isn't ready."""
    settings = _parse_database_url(url or DATABASE_URL)
    delay = 1
    for attempt in range(1, attempts + 1):
        try:
            return Connection(pymssql.connect(**settings, login_timeout=10))
        except pymssql.Error as error:
            if attempt == attempts:
                raise
            print(
                f"Database not reachable (attempt {attempt}/{attempts}), "
                f"retrying in {delay}s: {error}",
                flush=True,
            )
            time.sleep(delay)
            delay = min(delay * 2, 10)
