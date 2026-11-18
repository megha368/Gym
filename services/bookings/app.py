"""Bookings service: members and login, passes, bookings, the waitlist and the audit log,
served as a JSON API. The UI (static pages in ui/) calls it from the browser.
"""

from flask import Flask, g, request
from werkzeug.exceptions import HTTPException

from bookings.scheduling_client import SchedulingUnavailable
from config.settings import PORT, SECRET_KEY
from cors import setup_cors
from database.database import STARTUP_ATTEMPTS, get_connection
from database.migrations import apply_migrations
from observability import health_response, log, setup_request_logging


def create_app():
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY is not set (it signs login tokens)")

    app = Flask(__name__)
    setup_request_logging(app)
    setup_cors(app)

    # At startup: wait for the database (it may be paused on Azure) and bring its schema up to date
    conn = get_connection(attempts=STARTUP_ATTEMPTS)
    try:
        apply_migrations(conn)
    finally:
        conn.close()

    @app.before_request
    def open_connection():
        # /health opens its own connection (so it can answer 503 instead of crashing), and
        # OPTIONS requests are the browser's CORS check, which needs no database.
        if request.endpoint == "health" or request.method == "OPTIONS":
            return
        g.conn = get_connection()

    @app.teardown_request
    def close_connection(error):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    @app.get("/health")
    def health():
        return health_response()

    # Partial failure: if Scheduling can't be reached, answer 503 with a clear message.
    # Endpoints that only need Bookings' own data (login, passes) keep working as normal.
    @app.errorhandler(SchedulingUnavailable)
    def scheduling_unavailable(error):
        log.warning("Scheduling unavailable during %s %s: %s", request.method, request.path, error)
        return {
            "error": "The class schedule is temporarily unavailable, so nothing was changed. "
                     "Please try again in a minute."
        }, 503

    # Every error answers in JSON (Flask's default is an HTML page)
    @app.errorhandler(HTTPException)
    def http_error(error):
        return {"error": error.description}, error.code

    @app.errorhandler(Exception)
    def unexpected_error(error):
        log.exception("Unexpected error during %s %s", request.method, request.path)
        return {"error": "Something went wrong on our side."}, 500

    import routes

    app.register_blueprint(routes.bp)
    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=PORT)
