# This is the app factory: a function that builds a configured app. It lets tests build an app pointed at a temporary database 

from flask import Flask, g, session

from bookings import auth
from config.settings import SECRET_KEY, SEED_DEMO_DATA
from database.database import get_connection, init_db
from database.seed import seed_demo_data


def create_app(db_path=None, seed_demo=SEED_DEMO_DATA):
    app = Flask(__name__) # var app is now the website
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # blocks cross-site form posts
    app.config["DB_PATH"] = db_path

    init_db(db_path)
    if seed_demo:
        conn = get_connection(db_path)
        seed_demo_data(conn)
        conn.close()

    @app.before_request
    def open_connection():
        g.conn = get_connection(app.config["DB_PATH"])
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