"""Scheduling service: class types, instructors and sessions, served as a JSON API.

Other services (Bookings) and the UI ask this service about sessions over HTTP.
"""

from datetime import datetime

from flask import Flask, jsonify, request

from config.settings import PORT, SEED_DEMO_DATA
from database.database import get_connection, init_db
from database.seed import seed_demo_data
from scheduling import service
from scheduling.service import SchedulingError


def create_app(db_path=None, seed_demo=SEED_DEMO_DATA):
    app = Flask(__name__)

    init_db(db_path)
    if seed_demo:
        conn = get_connection(db_path)
        seed_demo_data(conn)
        conn.close()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/sessions")
    def list_sessions():
        """Upcoming scheduled sessions, soonest first. Optional ?from=<ISO time>."""
        from_param = request.args.get("from")
        try:
            now = datetime.fromisoformat(from_param) if from_param else None
        except ValueError:
            return {"error": "from must be an ISO datetime like 2026-11-16T18:00"}, 400
        conn = get_connection(db_path)
        try:
            return jsonify(service.list_upcoming_sessions(conn, now=now))
        finally:
            conn.close()

    @app.get("/sessions/<int:session_id>")
    def get_session(session_id):
        """One session with its class and instructor names, or 404 if it doesn't exist."""
        conn = get_connection(db_path)
        try:
            return service.get_session_details(conn, session_id)
        except SchedulingError as error:
            return {"error": str(error)}, 404
        finally:
            conn.close()

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=PORT)
