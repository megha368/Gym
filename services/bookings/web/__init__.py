# This is the app factory: a function that builds a configured app. It lets tests build an app pointed at a temporary database 

from flask import Flask, g, render_template, request, session

from bookings import auth
from bookings.scheduling_client import SchedulingUnavailable
from config.settings import SECRET_KEY
from database.database import STARTUP_ATTEMPTS, get_connection
from database.migrations import apply_migrations
from observability import health_response, log, setup_request_logging


def create_app():
    app = Flask(__name__) # var app is now the website
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # blocks cross-site form posts
    setup_request_logging(app)

    # At startup: wait for the database (it may be paused on Azure) and bring its schema up to date
    conn = get_connection(attempts=STARTUP_ATTEMPTS)
    try:
        apply_migrations(conn)
    finally:
        conn.close()

    @app.before_request
    def open_connection():
        if request.endpoint in ("health", "static"):
            return  # /health opens its own connection, so it can report 503 instead of crashing
        g.conn = get_connection()
        member_id = session.get("member_id")
        g.member = auth.get_member(g.conn, member_id) if member_id else None
        if member_id and g.member is None:
            session.clear()  # cookie points at a member that no longer exists

    @app.teardown_request
    def close_connection(error):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    @app.route("/health")
    def health():
        return health_response()

    # Partial failure: if Scheduling can't be reached, show a clear page instead of a crash.
    # Pages that only need Bookings' own data (log in, passes) keep working as normal.
    @app.errorhandler(SchedulingUnavailable)
    def scheduling_unavailable(error):
        log.warning("Scheduling unavailable during %s %s: %s", request.method, request.path, error)
        return render_template("unavailable.html"), 503

    from web import routes

    app.register_blueprint(routes.bp)
    return app