"""Team password (app/auth.py): off locally, required for every /api route once APP_PASSCODE is set."""

from fastapi.testclient import TestClient

from app import auth, config
from app.main import app


def _client(monkeypatch, password: str = "") -> TestClient:
    monkeypatch.setenv("APP_PASSCODE", password)
    monkeypatch.setenv("APP_SECRET", "test-secret")
    config.get_settings.cache_clear()
    return TestClient(app)


def test_no_password_means_no_login(session, monkeypatch):
    c = _client(monkeypatch)
    assert c.get("/api/auth/status").json() == {"required": False, "authenticated": False}
    assert c.get("/api/leads").status_code == 200


def test_password_gate(session, monkeypatch):
    c = _client(monkeypatch, "open-sesame")
    assert c.get("/api/leads").status_code == 401
    assert c.get("/api/leads").json()["error"]["code"] == "UNAUTHORIZED"
    assert c.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
    assert c.get("/api/leads").status_code == 401

    ok = c.post("/api/auth/login", json={"password": "open-sesame"})
    assert ok.status_code == 200 and auth.COOKIE in ok.cookies
    assert c.get("/api/leads").status_code == 200  # the cookie is sent from now on
    assert c.get("/api/auth/status").json() == {"required": True, "authenticated": True}

    c.post("/api/auth/logout")
    c.cookies.clear()
    assert c.get("/api/leads").status_code == 401
    # Shared report links stay public (they carry their own unguessable token).
    assert c.get("/api/reports/abc/file.pdf").status_code == 404


def test_tokens_expire_and_cannot_be_forged(monkeypatch):
    monkeypatch.setenv("APP_PASSCODE", "pw")
    monkeypatch.setenv("APP_SECRET", "s1")
    config.get_settings.cache_clear()
    token = auth.make_token(now=1_000_000)
    assert auth.token_valid(token, now=1_000_000 + 3600)
    assert not auth.token_valid(token, now=1_000_000 + 31 * 86400)  # older than 30 days
    issued, sig = token.split(".")
    assert not auth.token_valid(f"{int(issued) + 1}.{sig}", now=1_000_000)  # tampered time
    monkeypatch.setenv("APP_SECRET", "s2")
    config.get_settings.cache_clear()
    assert not auth.token_valid(token, now=1_000_000 + 60)  # new secret signs everyone out
