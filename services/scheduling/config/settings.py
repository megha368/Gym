import os

PORT = int(os.environ.get("PORT", 8001))
DATABASE_URL = os.environ.get("DATABASE_URL")  # secret, no default: mssql://user:password@host:port/database
SEED_DEMO_DATA = os.environ.get("SEED_DEMO_DATA", "1") == "1"
VERSION = os.environ.get("VERSION", "dev")  # the git commit SHA, set when the image is built

# The website the UI is served from; only it may call this service from a browser (CORS)
UI_ORIGIN = os.environ.get("UI_ORIGIN", "http://localhost:8080")
