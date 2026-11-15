import os

PORT = int(os.environ.get("PORT", 8000))
DATA_DIR = os.environ.get("DATA_DIR", "data")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me") # signs the login cookie so users can't forge it

# Where to find the Scheduling service, and how long to wait for it before giving up
SCHEDULING_URL = os.environ.get("SCHEDULING_URL", "http://localhost:8001")
SCHEDULING_TIMEOUT_S = float(os.environ.get("SCHEDULING_TIMEOUT_S", 2))
