"""CORS: which website may call this service from the browser.

Browsers only let a page call a service on another website (origin) if the service
answers with Access-Control-Allow-Origin naming that page's origin. We name exactly one:
the UI's origin, from UI_ORIGIN. Any other website's page is refused by the browser.
"""

from flask import request

from config.settings import UI_ORIGIN


def setup_cors(app):
    @app.after_request
    def add_cors_headers(response):
        if request.headers.get("Origin") == UI_ORIGIN:
            response.headers["Access-Control-Allow-Origin"] = UI_ORIGIN
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
            response.headers["Access-Control-Max-Age"] = "600"  # browser may cache this answer for 10 min
        response.headers["Vary"] = "Origin"
        return response
