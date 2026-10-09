"""End to end with fake AI providers (no network): upload → batch → worker stages → leads → AI vs Human."""

import io
import subprocess
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import config, providers
from app.db import get_engine
from app.main import app
from app.models import CallStage
from app.pipeline.stages import process_job
from app.worker import claim_job


@pytest.fixture
def fake_ai(monkeypatch):
    monkeypatch.setenv("TRANSCRIBER", "fake")
    monkeypatch.setenv("ANALYZER", "fake")
    config.get_settings.cache_clear()
    providers.reset_providers()
    yield
    providers.reset_providers()


def _tone(path, seconds: float) -> bytes:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-ac", "1", str(path)],
        check=True,
    )  # fmt: skip
    return path.read_bytes()


def _upload(client: TestClient, name: str, data: bytes) -> str:
    up = client.post("/api/uploads", json={"filename": name, "size": len(data), "mime": "audio/mpeg"}).json()
    size = up["chunk_size"]
    for i in range(up["total_chunks"]):
        r = client.put(f"/api/uploads/{up['upload_id']}/chunks/{i}", content=data[i * size : (i + 1) * size])
        assert r.status_code == 200, r.text
    done = client.post(f"/api/uploads/{up['upload_id']}/complete").json()
    assert done["status"] == "complete"
    return up["upload_id"]


async def _run_worker_until_idle() -> None:
    while True:
        did_work = False
        for stage in (
            CallStage.downloading,
            CallStage.preparing,
            CallStage.transcribing,
            CallStage.analysing,
        ):
            with Session(get_engine()) as s:
                job = claim_job(s, stage)
            if job:
                await process_job(job)
                did_work = True
        if not did_work:
            return


async def test_full_flow(session, fake_ai, tmp_path):
    client = TestClient(app)
    human = _tone(tmp_path / "human.mp3", 8)
    short = _tone(tmp_path / "short.mp3", 2)
    ai_zip = io.BytesIO()
    with zipfile.ZipFile(ai_zip, "w") as zf:
        zf.writestr("ai_call.mp3", _tone(tmp_path / "ai.mp3", 8))
        zf.writestr("readme.txt", "not audio")

    files = [
        {"upload_id": _upload(client, "human.mp3", human), "agent_type": "human"},
        {"upload_id": _upload(client, "short.mp3", short), "agent_type": "ai"},
        {"upload_id": _upload(client, "ai_calls.zip", ai_zip.getvalue()), "agent_type": "ai"},
    ]
    r = client.post(
        "/api/batches",
        json={"name": "Test", "campaign": "Follow-up", "agent_type_mode": "column", "files": files},
    )
    assert r.status_code == 200, r.text
    batch = r.json()
    assert batch["counts"]["total"] == 3
    assert batch["skipped_inputs"][0]["reason"] == "Not an audio or video file"

    await _run_worker_until_idle()

    detail = client.get(f"/api/batches/{batch['id']}").json()
    assert detail["status"] == "done"
    by_label = {c["label"]: c for c in detail["calls"]}
    assert by_label["human"]["status"] == "done"
    assert by_label["ai_call"]["status"] == "done"
    assert by_label["short"]["status"] == "skipped" and by_label["short"]["error_code"] == "TOO_SHORT"

    call = client.get(f"/api/calls/{by_label['human']['id']}").json()
    assert call["transcript"]["segments"][0]["role"] == "agent"
    assert call["analysis"]["intent"]["bucket"] == "high"
    assert call["analysis"]["objections"][0]["verified"] is True  # quote is really in the transcript
    assert (
        call["analysis"]["pitch_opportunities"][0]["verified"] is True
    )  # pitch rests on the customer's words
    assert call["analysis"]["quality_pct"] == 75.0  # all 4/5 → (4-1)/4
    assert call["metrics"]["agent_turns"] == 3
    audio = client.get(f"/api/calls/{by_label['human']['id']}/audio", headers={"Range": "bytes=0-99"})
    assert audio.status_code == 206 and len(audio.content) == 100

    leads = client.get("/api/leads").json()
    assert leads["total"] == 3
    kpis = client.get("/api/leads/kpis").json()
    assert kpis["intent"]["not_available"] == 1  # the too-short call

    lead_id = by_label["human"]["lead_id"]
    lead = client.get(f"/api/leads/{lead_id}").json()
    assert lead["path"]["next_actions"] and lead["actions"][0]["due_date"]  # "tomorrow" resolved to a date

    cmp = client.get("/api/compare").json()
    assert cmp["records"]["ai"]["uploaded"] == 2 and cmp["records"]["ai"]["not_connected"] == 1
    assert cmp["scores"]["human"]["avg_review"] == 4.0 and cmp["scores"]["ai"]["avg_review"] == 2.0
    assert cmp["synthesis"]["verdict_headline"]
    imp = cmp["improvement"]
    assert imp["verdict"]["status"] == "behind" and imp["verdict"]["readiness_pct"] == 50  # 2.0 vs 4.0
    assert imp["parameters"][0]["priority"] == "high" and imp["parameters"][0]["gap"] == 2.0
    assert imp["parameters"][0]["bot_examples"][0]["better"]  # each weak moment says what to do instead
    cause = imp["root_causes"][0]
    assert cause["pattern"] == "scripted_repeat" and cause["area"] == "Conversation flow" and cause["fix"]
    assert cause["calls"][0]["lead_id"] and cause["calls"][0]["better"]  # drillable to call + lead
    rca = imp["call_rca"][0]
    assert rca["issue_count"] == len(rca["issues"]) > 0
    assert imp["objections"][0]["type"] == "price" and imp["objections"][0]["human_example"]
    assert cmp["outdated_bot_reviews"] == 0  # reviewed with today's prompt
    assert client.post("/api/compare/update-bot-reviews").json() == {"queued": 0}
    change = cmp["synthesis"]["recommended_changes"][0]
    assert change["examples"] and all(
        e["call_id"] != 999999 for e in change["examples"]
    )  # unknown ids dropped
    assert cmp["sample_warning"]
    assert client.get("/api/compare/export.csv").text.startswith("call_id,label,agent_type")

    # Shareable report: Word file and print-ready page contain every section.
    import io as _io

    from docx import Document

    docx_res = client.get("/api/compare/export.docx")
    assert docx_res.status_code == 200 and docx_res.headers["content-disposition"].endswith('.docx"')
    text = "\n".join(p.text for p in Document(_io.BytesIO(docx_res.content)).paragraphs)
    for heading in (
        "Records",
        "Verdict",
        "Where they differ",
        "Review scores",
        "Measured from the transcripts",
        "Outcomes and customer mood",
        "Improvement plan for the bot",
        "Root causes — repeated bot failures",
        "Objections the bot missed",
        "Recommended changes to the bot",
        "Call-by-call RCA (bot calls)",
        "Every call",
    ):
        assert heading in text, heading
    page = client.get("/api/compare/report.html?print=1").text
    assert "Save as PDF" in page and "window.print()" in page and "Every call" in page

    # Swap speakers → metrics recomputed and analysis re-queued.
    client.post(f"/api/calls/{by_label['human']['id']}/swap-speakers")
    await _run_worker_until_idle()
    swapped = client.get(f"/api/calls/{by_label['human']['id']}").json()
    assert swapped["transcript"]["segments"][0]["role"] == "customer"
    assert swapped["status"] == "done"


async def test_unlabelled_transcripts_get_speakers_from_the_llm():
    """Local Whisper returns speaker "?"; the analyser labels each line agent/customer."""
    from app.pipeline.analysis import assign_speakers

    segs = [{"speaker": "?", "start": float(i), "end": i + 0.9, "text": t}
            for i, t in enumerate(["Hello, Sleep Company se", "Haan boliye", "Offer hai"])]  # fmt: skip
    out = await assign_speakers(segs, "roman")
    assert [s["role"] for s in out] == ["agent", "customer", "agent"]
    assert out[0]["original_text"] == "Hello, Sleep Company se"


async def test_transcript_cache_is_per_transcriber(session, fake_ai, tmp_path):
    """Same audio again, but the old transcript came from a different transcriber → transcribe afresh."""
    from sqlmodel import select

    from app.models import Transcript

    client = TestClient(app)
    data = _tone(tmp_path / "a.mp3", 8)

    up = _upload(client, "a.mp3", data)
    client.post("/api/batches", json={"agent_type_mode": "human", "files": [{"upload_id": up}]})
    await _run_worker_until_idle()
    first = session.exec(select(Transcript)).one()
    first.provider = "faster_whisper"  # as if it had been made before switching to the current transcriber
    session.add(first)
    session.commit()

    up = _upload(client, "a.mp3", data)
    client.post("/api/batches", json={"agent_type_mode": "human", "files": [{"upload_id": up}]})
    await _run_worker_until_idle()
    second = session.exec(select(Transcript).where(Transcript.id != first.id)).one()
    assert second.provider == "fake"  # made by the current transcriber, not copied from the old one
