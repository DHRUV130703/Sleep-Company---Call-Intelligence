"""Processing inside web requests (pipeline/tick.py) — what runs on Vercel, where there is no worker."""

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.pipeline import stage_transcribe
from app.providers.assemblyai import AssemblyAITranscriber
from tests.test_assemblyai import fake_server
from tests.test_pipeline_fake_providers import _tone, _upload


def _batch(client: TestClient, tmp_path) -> dict:
    files = [
        {"upload_id": _upload(client, "human.mp3", _tone(tmp_path / "h.mp3", 8)), "agent_type": "human"},
        {"upload_id": _upload(client, "bot.mp3", _tone(tmp_path / "a.mp3", 9)), "agent_type": "ai"},
    ]
    r = client.post(
        "/api/batches", json={"name": "T", "campaign": "", "agent_type_mode": "column", "files": files}
    )
    assert r.status_code == 200, r.text
    return r.json()


def _tick_until_idle(client: TestClient, limit: int = 60) -> list[dict]:
    seen = []
    for _ in range(limit):
        r = client.post("/api/process/tick").json()
        assert r["enabled"] is True
        if r["processed"]:
            seen.append(r["processed"])
        elif r["queued"] == 0 and r["running"] == 0:
            return seen
    raise AssertionError("processing never finished")


def test_ticks_are_off_unless_enabled(session):
    assert TestClient(app).post("/api/process/tick").json() == {"enabled": False}


def test_ticks_process_a_whole_batch_without_a_worker(session, fake_ai, monkeypatch, tmp_path):
    monkeypatch.setenv("PROCESS_IN_REQUESTS", "true")
    config.get_settings.cache_clear()
    client = TestClient(app)
    batch = _batch(client, tmp_path)

    steps = _tick_until_idle(client)

    assert {s["stage"] for s in steps} == {"preparing", "transcribing", "analysing"}
    detail = client.get(f"/api/batches/{batch['id']}").json()
    assert detail["status"] == "done" and all(c["status"] == "done" for c in detail["calls"])


def test_assemblyai_is_sent_then_checked_back_in_short_steps(session, fake_ai, monkeypatch, tmp_path):
    monkeypatch.setenv("PROCESS_IN_REQUESTS", "true")
    config.get_settings.cache_clear()
    transport, calls = fake_server(
        {"status": "completed", "utterances": [
            {"speaker": "A", "start": 0, "end": 3000, "text": "Namaste, The Sleep Company se."},
            {"speaker": "B", "start": 3200, "end": 6000, "text": "Haan ji, price batao."},
        ]},
        polls_before_done=1,
    )  # fmt: skip
    bot = AssemblyAITranscriber("test-key", ["universal-2"], transport=transport)
    monkeypatch.setattr(stage_transcribe, "_stepwise_transcriber", lambda: bot)
    monkeypatch.setattr(stage_transcribe, "CHECK_AGAIN_S", 0)
    client = TestClient(app)
    batch = _batch(client, tmp_path)

    steps = [s["stage"] for s in _tick_until_idle(client)]

    # Call 1: send (wait) → check: "processing" (wait) → check: done. The fake server answers "processing"
    # only once in total, so call 2 is: send (wait) → check: done. Each step is its own short request.
    assert steps.count("transcribing") == 5 and calls["polls"] == 3
    detail = client.get(f"/api/batches/{batch['id']}").json()
    assert all(c["status"] == "done" for c in detail["calls"])
    call = client.get(f"/api/calls/{detail['calls'][0]['id']}").json()
    assert call["transcript"]["provider"] == "assemblyai"
    assert call["transcript"]["segments"][1]["text"] == "Haan ji, price batao."
