"""Request logging and the health check, set up the same way in each service.

Logs go to stdout (the terminal, or `docker compose logs`, or Azure's log stream), one line
per request: method, path, status code and how long it took.
"""

import logging
import sys
import time

from flask import g, request

from config.settings import VERSION
from database.database import check_database

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("requests")


def setup_request_logging(app):
    @app.before_request
    def start_timer():
        g.request_started = time.perf_counter()

    @app.after_request
    def log_request(response):
        started = g.get("request_started", time.perf_counter())
        duration_ms = (time.perf_counter() - started) * 1000
        log.info("%s %s %s %.0fms", request.method, request.path, response.status_code, duration_ms)
        return response


def health_response():
    """GET /health: 200 if this service can read and write its own database, 503 if not.

    Only this service's own state counts: it does not check the other service.
    """
    try:
        check_database()
        return {"status": "ok", "db": "ok", "version": VERSION}, 200
    except Exception as error:  # any failure means "not healthy"; the reason goes to the log
        log.warning("Health check failed: %s", error)
        return {"status": "error", "db": "error", "version": VERSION}, 503
