import os

PORT = int(os.environ.get("PORT", 5000))
DATA_DIR = os.environ.get("DATA_DIR", "data")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me") # signs the login cookie so users can't forge it 
SEED_DEMO_DATA = os.environ.get("SEED_DEMO_DATA", "1") == "1"