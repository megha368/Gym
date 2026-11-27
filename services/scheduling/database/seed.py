"""Demo data, so the schedule is never empty.

On every start, the Scheduling service calls seed_demo_data(). The first time, it creates
the demo class types and instructors. Every time, it adds the day's sessions to each of the
next 7 days that has none yet. On Azure the service starts again after every idle period
(scale to zero), so this keeps a week of classes ahead without anyone touching it.
Calling it again on the same day adds nothing, so it is safe to run on every start.
"""

from datetime import datetime, timedelta

from scheduling import service as scheduling_service

CLASSES = [
    ("Vinyasa Yoga", "Flowing yoga linked with breath"),
    ("Pilates", "Core strength and control"),
    ("HIIT", "High-intensity interval training"),
    ("Spin", "Indoor cycling"),
    ("Restorative Yoga", "Slow stretching and relaxation"),
]
INSTRUCTORS = ["Sarah", "Diego", "Priya"]
# (class index, instructor index, start hour, capacity): 5 sessions per day
DAILY_SLOTS = [(0, 0, 7, 12), (1, 2, 12, 10), (2, 1, 18, 15), (3, 1, 19, 1), (4, 2, 20, 12)]
DAYS_AHEAD = 7


def _ids_by_name(conn, table):
    # Setup script, not business logic, so direct queries are fine here
    return {row["name"]: row["id"] for row in conn.execute(f"SELECT id, name FROM {table}").fetchall()}


def _day_has_sessions(conn, day):
    next_day = day + timedelta(days=1)
    return conn.execute(
        "SELECT COUNT(*) AS n FROM sessions WHERE start_time >= %s AND start_time < %s",
        (day.isoformat(), next_day.isoformat()),
    ).fetchone()["n"] > 0


def seed_demo_data(conn, now=None):
    """Top the schedule up to a week ahead. Returns how many sessions it added."""
    now = now or datetime.now()

    if conn.execute("SELECT COUNT(*) AS n FROM class_types").fetchone()["n"] == 0:
        for name, description in CLASSES:
            scheduling_service.create_class_type(conn, name, description)
        for name in INSTRUCTORS:
            scheduling_service.create_instructor(conn, name)
    class_ids = _ids_by_name(conn, "class_types")
    instructor_ids = _ids_by_name(conn, "instructors")

    added = 0
    for offset in range(1, DAYS_AHEAD + 1):  # starting tomorrow, so every session is upcoming
        day = (now + timedelta(days=offset)).date()
        if _day_has_sessions(conn, day):
            continue
        for class_index, instructor_index, hour, capacity in DAILY_SLOTS:
            class_id = class_ids.get(CLASSES[class_index][0])
            instructor_id = instructor_ids.get(INSTRUCTORS[instructor_index])
            if class_id is None or instructor_id is None:
                continue  # someone renamed or removed a demo class or instructor
            start = datetime(day.year, day.month, day.day, hour)
            scheduling_service.create_session(
                conn, class_id, instructor_id, start.isoformat(timespec="minutes"), capacity
            )
            added += 1
    return added
