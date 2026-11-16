"""Applies the numbered SQL files in migrations/ that this database hasn't had yet.

Every applied file is recorded in the schema_migrations table, so each migration runs
exactly once: a second startup finds nothing new and changes nothing.
"""

import os
import re

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")


def _split_batches(sql):
    """Split a script on lines that contain only GO, like SQL Server's own tools do."""
    batches = re.split(r"^\s*GO\s*$", sql, flags=re.IGNORECASE | re.MULTILINE)
    return [batch for batch in batches if batch.strip()]


def apply_migrations(conn, directory=MIGRATIONS_DIR):
    """Apply pending migrations in filename order. Returns the names of the ones applied."""
    conn.execute(
        """
        IF OBJECT_ID('schema_migrations') IS NULL
            CREATE TABLE schema_migrations (
                version    NVARCHAR(255) PRIMARY KEY,
                applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
        """
    )
    conn.commit()

    applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    pending = sorted(f for f in os.listdir(directory) if f.endswith(".sql") and f not in applied)

    for filename in pending:
        with open(os.path.join(directory, filename), encoding="utf-8") as file:
            sql = file.read()
        try:
            # The migration and its record in schema_migrations are one transaction:
            # either both happen, or (on any error) neither does.
            for batch in _split_batches(sql):
                conn.execute(batch)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (filename,))
            conn.commit()
        except Exception:
            conn.rollback()
            print(f"Migration {filename} FAILED and was rolled back", flush=True)
            raise
        print(f"Applied migration {filename}", flush=True)

    if not pending:
        print("Database schema is up to date, no migrations to apply", flush=True)
    return pending
