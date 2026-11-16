# This is the app factory: a function that builds a configured app. It lets tests build an app pointed at a temporary database 

from flask import Flask, g, session

from bookings import auth
from config.settings import SECRET_KEY
from database.database import STARTUP_ATTEMPTS, get_connection
from database.migrations import apply_migrations


def create_app():
    app = Flask(__name__) # var app is now the website
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # blocks cross-site form posts

    # At startup: wait for the database (it may be paused on Azure) and bring its schema up to date
    conn = get_connection(attempts=STARTUP_ATTEMPTS)
    try:
        apply_migrations(conn)
    finally:
        conn.close()

    @app.before_request
    def open_connection():
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
        return {"status": "ok"} # if server replies with status: ok, the system knows the app is healthy  

    from web import routes

    app.register_blueprint(routes.bp)
    return app