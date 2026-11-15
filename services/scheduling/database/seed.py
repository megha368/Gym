# The schedule would be empty on first run, so this fills an empty database with a week of sample classes 

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
# (class index, instructor index, start hour, capacity): 5 slots x 7 days = 35 sessions
DAILY_SLOTS = [(0, 0, 7, 12), (1, 2, 12, 10), (2, 1, 18, 15), (3, 1, 19, 1), (4, 2, 20, 12)]


def seed_demo_data(conn, now=None):
    """Fill an empty database with a week of sample sessions. Returns True if it seeded."""
    now = now or datetime.now()
    # Setup script, not business logic, so a direct check is fine here
    if conn.execute("SELECT COUNT(*) FROM class_types").fetchone()[0] > 0:
        return False

    class_ids = [scheduling_service.create_class_type(conn, n, d) for n, d in CLASSES]
    instructor_ids = [scheduling_service.create_instructor(conn, n) for n in INSTRUCTORS]

    for day in range(1, 8):  # starting tomorrow, so every session is upcoming
        for class_index, instructor_index, hour, capacity in DAILY_SLOTS:
            start = (now + timedelta(days=day)).replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            scheduling_service.create_session(
                conn,
                class_ids[class_index],
                instructor_ids[instructor_index],
                start.isoformat(timespec="minutes"),
                capacity,
            )
    return True