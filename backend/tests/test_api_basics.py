from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_every_check(session):
    with TestClient(app) as client:
        body = client.get("/api/health").json()
    names = {c["name"] for c in body["checks"]}
    assert {
        "database",
        "worker",
        "ffmpeg",
        "ffprobe",
        "transcriber",
        "analyzer",
        "config",
        "storage",
    } <= names
    by_name = {c["name"]: c for c in body["checks"]}
    assert by_name["transcriber"]["state"] == "ok"  # fake provider in tests
    # No worker running in tests → health fails with a helpful hint.
    assert by_name["worker"]["state"] == "fail" and "make worker" in by_name["worker"]["detail"]


def test_stats_on_empty_database(session):
    with TestClient(app) as client:
        body = client.get("/api/stats").json()
    assert body == {"total_calls": 0, "analysed_calls": 0, "audio_seconds": 0.0, "last_processed_at": None}


def test_settings_include_scorecard_and_rubric(session):
    with TestClient(app) as client:
        body = client.get("/api/settings").json()
    assert body["transcriber"]["selected"] == "fake"
    assert body["analyzer"]["selected"] == "fake"
    assert len(body["scorecard"]["dimensions"]) == 10


def test_unknown_route_uses_standard_error_shape(session):
    with TestClient(app) as client:
        res = client.get("/api/does-not-exist")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
