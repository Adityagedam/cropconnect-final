# Pytest integration coverage for the auth profile flow with mocked DB connections.
from fastapi.testclient import TestClient

import esp32_ingest as api


def test_signup_login_and_profile_fetch(fake_db):
    client = TestClient(api.app)
    payload = {
        "name": "Test Farmer",
        "email": "farmer@example.com",
        "password": "correct-password",
        "phone": "9999999999",
        "state": "Maharashtra",
        "location": "Pune",
        "land_size": 2,
    }

    signup = client.post("/api/auth/signup", json=payload)
    assert signup.status_code == 200
    assert signup.json()["user"]["email"] == "farmer@example.com"

    login = client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert login.status_code == 200

    profile = client.get("/api/auth/profile")
    assert profile.status_code == 200
    assert profile.json()["user"]["email"] == "farmer@example.com"
    assert len(fake_db["users"]) == 1


def test_duplicate_signup_returns_409(fake_db):
    client = TestClient(api.app)
    payload = {
        "name": "Test Farmer",
        "email": "farmer@example.com",
        "password": "correct-password",
        "phone": "9999999999",
        "state": "Maharashtra",
        "location": "Pune",
        "land_size": 2,
    }

    assert client.post("/api/auth/signup", json=payload).status_code == 200
    duplicate = client.post("/api/auth/signup", json=payload)
    assert duplicate.status_code == 409


def test_rate_limit_enforcement(fake_db):
    api.rate_limit_named_key("pytest", "client", limit=1, window_seconds=60)
    try:
        api.rate_limit_named_key("pytest", "client", limit=1, window_seconds=60)
    except api.HTTPException as exc:
        assert exc.status_code == 429
    else:
        raise AssertionError("Expected rate limiter to reject the second request")
