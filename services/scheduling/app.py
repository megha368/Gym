"""Scheduling service: class types, instructors and sessions, served as a JSON API.

Other services (Bookings) and the UI ask this service about sessions over HTTP.
"""

from datetime import datetime

from flask import Flask, jsonify, request

from config.settings import PORT, SEED_DEMO_DATA
from cors import setup_cors
from database.database import STARTUP_ATTEMPTS, get_connection
from database.migrations import apply_migrations
from database.seed import seed_demo_data
from observability import health_response, setup_request_logging
from scheduling import service
from scheduling.service import SchedulingError


def create_app(seed_demo=SEED_DEMO_DATA):
    app = Flask(__name__)
    setup_request_logging(app)
    setup_cors(app)

    # At startup: wait for the database (it may be paused on Azure), bring its schema
    # up to date, and add the demo classes if the database is empty.
    conn = get_connection(attempts=STARTUP_ATTEMPTS)
    try:
        apply_migrations(conn)
        if seed_demo:
            seed_demo_data(conn)
    finally:
        conn.close()

    @app.get("/health")
    def health():
        return health_response()

    @app.get("/sessions")
    def list_sessions():
        """Upcoming scheduled sessions, soonest first. Optional ?from=<ISO time>."""
        from_param = request.args.get("from")
        try:
            now = datetime.fromisoformat(from_param) if from_param else None
        except ValueError:
            return {"error": "from must be an ISO datetime like 2026-11-16T18:00"}, 400
        conn = get_connection()
        try:
            return jsonify(service.list_upcoming_sessions(conn, now=now))
        finally:
            conn.close()

    @app.get("/sessions/<int:session_id>")
    def get_session(session_id):
        """One session with its class and instructor names, or 404 if it doesn't exist."""
        conn = get_connection()
        try:
            return service.get_session_details(conn, session_id)
        except SchedulingError as error:
            return {"error": str(error)}, 404
        finally:
            conn.close()

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=PORT)
