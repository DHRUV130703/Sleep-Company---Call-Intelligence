"""Sign-in (app/auth.py): off locally; with APP_USERS set, every /api route needs a signed-in person."""

import json

from fastapi.testclient import TestClient

from app import auth, config
from app.main import app

USERS = {"Dhruv.Gohil@thesleepcompany.in": "pw-one", "ashish.kumar@thesleepcompany.in": "pw-two"}


def _client(monkeypatch, accounts: dict | None = None) -> TestClient:
    monkeypatch.setenv("APP_USERS", json.dumps(accounts) if accounts else "")
    monkeypatch.setenv("APP_SECRET", "test-secret")
    config.get_settings.cache_clear()
    return TestClient(app)


def _login(c: TestClient, email: str, password: str) -> int:
    return c.post("/api/auth/login", json={"email": email, "password": password}).status_code


def test_no_accounts_means_no_login(session, monkeypatch):
    c = _client(monkeypatch)
    assert c.get("/api/auth/status").json() == {"required": False, "authenticated": False, "email": None}
    assert c.get("/api/leads").status_code == 200


def test_each_person_signs_in_with_their_own_email_and_password(session, monkeypatch):
    c = _client(monkeypatch, USERS)
    assert c.get("/api/leads").status_code == 401
    assert _login(c, "dhruv.gohil@thesleepcompany.in", "pw-two") == 401  # someone else's password
    assert _login(c, "nobody@thesleepcompany.in", "pw-one") == 401
    assert c.get("/api/leads").status_code == 401

    assert _login(c, "  DHRUV.GOHIL@thesleepcompany.in ", "pw-one") == 200  # email case/spaces don't matter
    assert c.get("/api/leads").status_code == 200
    assert c.get("/api/auth/status").json()["email"] == "dhruv.gohil@thesleepcompany.in"

    c.post("/api/auth/logout")
    c.cookies.clear()
    assert c.get("/api/leads").status_code == 401
    assert _login(c, "ashish.kumar@thesleepcompany.in", "pw-two") == 200
    assert c.get("/api/auth/status").json()["email"] == "ashish.kumar@thesleepcompany.in"
    # Shared report links stay public (they carry their own unguessable token).
    assert c.get("/api/reports/abc/file.pdf").status_code == 404


def test_sessions_expire_and_end_when_access_is_removed(monkeypatch):
    monkeypatch.setenv("APP_USERS", json.dumps(USERS))
    monkeypatch.setenv("APP_SECRET", "s1")
    config.get_settings.cache_clear()
    email = "ashish.kumar@thesleepcompany.in"
    token = auth.make_token(email, now=1_000_000)
    assert auth.signed_in_email(token, now=1_000_000 + 3600) == email
    assert auth.signed_in_email(token, now=1_000_000 + 31 * 86400) is None  # older than 30 days
    assert auth.signed_in_email(token.replace(email, "dhruv.gohil@thesleepcompany.in"), now=1_000_060) is None
    monkeypatch.setenv("APP_USERS", json.dumps({**USERS, email: "changed"}))  # new password
    config.get_settings.cache_clear()
    assert auth.signed_in_email(token, now=1_000_060) is None
    monkeypatch.setenv("APP_USERS", "not json")  # a broken setting locks everyone out, never opens up
    config.get_settings.cache_clear()
    assert auth.auth_required() and auth.signed_in_email(token, now=1_000_060) is None
