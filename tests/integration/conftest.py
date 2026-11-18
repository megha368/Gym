"""Integration tests: they talk to the whole system started with `docker compose up`,
over real HTTP, exactly like the browser does. Nothing is replaced by a stub here.

    docker compose up -d --build
    pip install -r tests/integration/requirements.txt
    pytest tests/integration
"""

import os
import uuid

import pytest
import requests

SCHEDULING_URL = os.environ.get("SCHEDULING_URL", "http://localhost:8001")
BOOKINGS_URL = os.environ.get("BOOKINGS_URL", "http://localhost:8000")
TIMEOUT_S = 10


@pytest.fixture
def member():
    """A brand-new member with a class pack; returns their Authorization header."""
    email = f"it-{uuid.uuid4().hex[:10]}@example.com"  # unique, so tests can run repeatedly
    response = requests.post(
        f"{BOOKINGS_URL}/auth/register",
        json={"name": "Integration Test", "email": email, "password": "secret123"},
        timeout=TIMEOUT_S,
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.json()['token']}"}
    response = requests.post(f"{BOOKINGS_URL}/passes", json={"pass_type": "class_pack"}, headers=headers, timeout=TIMEOUT_S)
    assert response.status_code == 201, response.text
    return headers
