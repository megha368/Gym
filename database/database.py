import os
import sqlite3

from config.settings import DATA_DIR


def get_connection(db_path=None):
    """Open a connection to the SQLite file """
    if db_path is None:
        os.makedirs(DATA_DIR, exist_ok=True) # makes sure the folder where your database lives actually exists on your computer. If the folder isn't there yet, it creates it.
        db_path = os.path.join(DATA_DIR, "gym.db") # sets the file path to gym.db 
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row # lets you read results by column name (like row["capacity"]) instead of by position 
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_scheduling_tables(conn):
    """Tables owned by the Class Scheduling domain."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS class_types (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS instructors (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            class_type_id INTEGER NOT NULL REFERENCES class_types(id),
            instructor_id INTEGER NOT NULL REFERENCES instructors(id),
            start_time    TEXT NOT NULL,
            capacity      INTEGER NOT NULL CHECK (capacity > 0),
            status        TEXT NOT NULL DEFAULT 'scheduled'
                          CHECK (status IN ('scheduled', 'cancelled'))
        );
    """)
    conn.commit()


def create_booking_tables(conn):
    """Tables owned by the Members & Bookings domain."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS passes (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id      INTEGER NOT NULL REFERENCES members(id),
            type           TEXT NOT NULL
                           CHECK (type IN ('drop_in', 'class_pack', 'membership')),
            remaining_uses INTEGER
                           CHECK (remaining_uses IS NULL OR remaining_uses >= 0),
            expires_at     TEXT,
            created_at     TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- session_id is deliberately NOT a foreign key (see ADR-3)
        CREATE TABLE IF NOT EXISTS bookings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id  INTEGER NOT NULL REFERENCES members(id),
            session_id INTEGER NOT NULL,
            pass_id    INTEGER NOT NULL REFERENCES passes(id),
            status     TEXT NOT NULL DEFAULT 'confirmed'
                       CHECK (status IN ('confirmed', 'cancelled')),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE UNIQUE INDEX IF NOT EXISTS one_confirmed_booking_per_session
            ON bookings (member_id, session_id) WHERE status = 'confirmed';

        CREATE TABLE IF NOT EXISTS waitlist_entries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id  INTEGER NOT NULL REFERENCES members(id),
            session_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (member_id, session_id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id  INTEGER NOT NULL REFERENCES members(id),
            action     TEXT NOT NULL,
            session_id INTEGER NOT NULL,
            details    TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()


def init_db(db_path=None):
    """Create every table the app needs. Safe to run on every startup."""
    conn = get_connection(db_path)
    create_scheduling_tables(conn)
    create_booking_tables(conn) 
    # Day 3: create_booking_tables(conn) goes here
    conn.close()