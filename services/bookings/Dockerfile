# Image for the bookings service.
# Pinned base image: the exact same Python every time it is built.
FROM python:3.12.8-slim-bookworm

# Don't write .pyc files, and print logs immediately instead of buffering them
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Dependencies first, on their own: Docker caches this step and only re-runs it
#    when requirements.txt changes, so rebuilding after a code change is fast.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Then the code, named file by file and folder by folder (no "COPY . ."), so tests,
#    caches and any .env file can never end up in the image.
COPY app.py routes.py observability.py cors.py ./
COPY config/ config/
COPY database/ database/
COPY migrations/ migrations/
COPY bookings/ bookings/

# 3. Run as an ordinary user, not root: if someone broke into the app, they couldn't
#    change the system inside the container.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# The git commit this image was built from (passed in by the pipeline), shown by /health
ARG VERSION=dev
ENV VERSION=$VERSION \
    PORT=8000

EXPOSE 8000

# gunicorn is a production web server (Flask's built-in one is for development only).
#   --workers 1   one process, so the migrations at startup can never run twice at once
#   --threads 4   it can still handle 4 requests at the same time
#   --timeout 120 startup may wait ~1 minute for a paused Azure database to wake up
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 'app:create_app()'"]
