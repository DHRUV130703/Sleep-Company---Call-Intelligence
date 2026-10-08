"""AssemblyAI integration against a fake AssemblyAI server (no network, no key needed)."""

import json

import httpx
import pytest

from app.providers import assemblyai
from app.providers.assemblyai import AssemblyAITranscriber
from app.providers.base import ProviderError


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch):
    monkeypatch.setattr(assemblyai, "POLL_EVERY_S", 0)


def fake_server(final: dict, polls_before_done: int = 1, upload_status: int = 200):
    calls = {"submit": None, "polls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"] == "test-key"
        if req.url.path == "/v2/upload":
            if upload_status != 200:
                return httpx.Response(upload_status, json={"error": "Invalid API key"})
            return httpx.Response(200, json={"upload_url": "https://cdn.test/audio"})
        if req.url.path == "/v2/transcript" and req.method == "POST":
            calls["submit"] = json.loads(req.content)
            return httpx.Response(200, json={"id": "t1", "status": "queued"})
        if req.url.path == "/v2/transcript/t1":
            calls["polls"] += 1
            if calls["polls"] <= polls_before_done:
                return httpx.Response(200, json={"id": "t1", "status": "processing"})
            return httpx.Response(200, json={"id": "t1", **final})
        return httpx.Response(404)

    return httpx.MockTransport(handler), calls


async def test_transcribes_with_speaker_turns(tmp_path):
    audio = tmp_path / "call.mp3"
    audio.write_bytes(b"ID3fake")
    transport, calls = fake_server({
        "status": "completed",
        "utterances": [
            {"speaker": "A", "start": 1300, "end": 9000, "text": "Good evening, The Sleep Company se bol rahi hoon."},
            {"speaker": "B", "start": 9400, "end": 12100, "text": "Haan ji, mattress ka price batao."},
            {"speaker": "A", "start": 12500, "end": 13000, "text": "  "},
        ],
    })  # fmt: skip
    t = AssemblyAITranscriber("test-key", ["universal-3-5-pro", "universal-2"], transport=transport)
    result = await t.transcribe(audio, script="roman")

    assert [(s.speaker, s.start, s.end) for s in result.segments] == [("A", 1.3, 9.0), ("B", 9.4, 12.1)]
    body = calls["submit"]
    assert body["speech_models"] == ["universal-3-5-pro", "universal-2"]
    assert body["speaker_labels"] is True and body["speakers_expected"] == 2
    assert body["language_detection"] is True and "SmartGRID" in body["keyterms_prompt"]
    assert calls["polls"] == 2  # waited while "processing"


async def test_out_of_credit_is_reported_clearly(tmp_path):
    audio = tmp_path / "call.mp3"
    audio.write_bytes(b"x")
    transport, _ = fake_server({"status": "error", "error": "Your account balance is insufficient"})
    with pytest.raises(ProviderError) as e:
        await AssemblyAITranscriber("test-key", ["universal-2"], transport=transport).transcribe(
            audio, script="roman"
        )
    assert e.value.no_credits


async def test_bad_key_is_not_retried(tmp_path):
    audio = tmp_path / "call.mp3"
    audio.write_bytes(b"x")
    transport, _ = fake_server({}, upload_status=401)
    with pytest.raises(ProviderError) as e:
        await AssemblyAITranscriber("test-key", ["universal-2"], transport=transport).transcribe(
            audio, script="roman"
        )
    assert e.value.no_credits and not e.value.retryable


async def test_missing_key_gives_a_clear_message(tmp_path, monkeypatch):
    from app import config, providers

    monkeypatch.setenv("TRANSCRIBER", "assemblyai")
    monkeypatch.setenv("TRANSCRIBER_FALLBACK", "none")
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "")
    config.get_settings.cache_clear()
    providers.reset_providers()
    with pytest.raises(ProviderError, match="ASSEMBLYAI_API_KEY is empty"):
        await providers.get_transcriber().transcribe(tmp_path / "x.mp3", script="roman")
