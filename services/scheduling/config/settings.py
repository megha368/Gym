import os

PORT = int(os.environ.get("PORT", 8001))
DATABASE_URL = os.environ.get("DATABASE_URL")  # secret, no default: mssql://user:password@host:port/database
SEED_DEMO_DATA = os.environ.get("SEED_DEMO_DATA", "1") == "1"
