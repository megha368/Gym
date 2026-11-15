import os

PORT = int(os.environ.get("PORT", 8001))
DATA_DIR = os.environ.get("DATA_DIR", "data")
SEED_DEMO_DATA = os.environ.get("SEED_DEMO_DATA", "1") == "1"
