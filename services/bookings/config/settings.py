import os

PORT = int(os.environ.get("PORT", 8000))
DATABASE_URL = os.environ.get("DATABASE_URL")  # secret, no default: mssql://user:password@host:port/database
SECRET_KEY = os.environ.get("SECRET_KEY")      # secret, no default: signs login tokens
VERSION = os.environ.get("VERSION", "dev")     # the git commit SHA, set when the image is built

# The website the UI is served from; only it may call this service from a browser (CORS)
UI_ORIGIN = os.environ.get("UI_ORIGIN", "http://localhost:8080")

# Where to find the Scheduling service, and how long to wait for it before giving up
SCHEDULING_URL = os.environ.get("SCHEDULING_URL", "http://localhost:8001")
SCHEDULING_TIMEOUT_S = float(os.environ.get("SCHEDULING_TIMEOUT_S", 2))
