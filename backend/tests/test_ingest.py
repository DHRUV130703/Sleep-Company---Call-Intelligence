import hashlib
import zipfile
from pathlib import Path

import httpx
import pytest

from app.errors import AppError
from app.ingest import chunks, sheet_reader, zip_reader
from app.ingest.downloader import direct_link, download
from app.pipeline.errors import StageError

# ---------------------------------------------------------------------------
# ZIP
# ---------------------------------------------------------------------------


def _zip(tmp_path, entries: dict[str, bytes]):
    path = tmp_path / "in.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return path


def test_zip_extracts_only_audio_and_explains_skips(tmp_path):
    path = _zip(tmp_path, {
        "calls/a1.mp3": b"x" * 100,
        "calls/notes.pdf": b"pdf",
        "__MACOSX/calls/._a1.mp3": b"junk",
        "../../evil.mp3": b"evil",
        "manifest.csv": b"file,agent type,phone\na1.mp3,AI bot,9037125616\n",
    })  # fmt: skip
    result = zip_reader.extract_audio(path, tmp_path / "out", max_entries=100)
    assert [e.name for e in result.entries] == ["calls/a1.mp3"]
    assert result.entries[0].meta["agent_type"] == "AI bot"
    assert result.entries[0].meta["lead_phone"] == "9037125616"
    reasons = {s["name"]: s["reason"] for s in result.skipped}
    assert reasons["calls/notes.pdf"] == "Not an audio or video file"
    assert reasons["../../evil.mp3"] == "Unsafe path inside the ZIP"
    # Extracted under our own random name, never the name from the archive.
    assert result.entries[0].path.parent == tmp_path / "out"


def test_zip_bomb_is_refused(tmp_path):
    path = _zip(tmp_path, {"big.wav": b"\0" * 5_000_000})  # compresses ~1000×
    with pytest.raises(AppError, match="unsafe size"):
        zip_reader.extract_audio(path, tmp_path / "out", max_entries=100)


def test_not_a_zip(tmp_path):
    p = tmp_path / "x.zip"
    p.write_bytes(b"not a zip")
    with pytest.raises(AppError):
        zip_reader.extract_audio(p, tmp_path / "out", max_entries=10)


# ---------------------------------------------------------------------------
# Spreadsheets
# ---------------------------------------------------------------------------


def test_sheet_mapping_and_validation(tmp_path):
    p = tmp_path / "calls.csv"
    p.write_text(
        "Call ID,Recording Link,Caller Type,Customer Name,Mobile\n"
        "c1,https://x.test/a.mp4,AI Bot,Nithin,9037125616\n"
        "c2,https://x.test/b.mp4,Human,Priya,9811122233\n"
        "c3,https://x.test/a.mp4,AI Bot,Dup,1\n"
        "c4,not-a-link,Human,Bad,2\n"
        "c5,https://x.test/c.mp4,robot-ish?,Odd,3\n"
    )
    headers, rows = sheet_reader.read_table(p)
    mapping = sheet_reader.suggest_mapping(headers, rows)
    assert mapping["recording_url"] == "Recording Link"
    assert mapping["agent_type"] == "Caller Type"
    assert mapping["lead_name"] == "Customer Name"
    assert mapping["lead_phone"] == "Mobile"
    assert mapping["external_id"] == "Call ID"

    check = sheet_reader.rows_to_specs(rows, mapping, "column")
    assert [s.agent_type for s in check.specs] == ["ai", "human", "ai"]  # "robot-ish?" → contains "bot"
    assert check.duplicates == 1
    assert check.problems == [{"row": 5, "message": "Missing or invalid link"}]


def test_xlsx_is_read(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["url", "phone"])
    ws.append(["https://x.test/a.mp3", 9037125616])
    p = tmp_path / "calls.xlsx"
    wb.save(p)
    headers, rows = sheet_reader.read_table(p)
    assert rows == [{"url": "https://x.test/a.mp3", "phone": "9037125616"}]


@pytest.mark.parametrize(("raw", "expected"), [
    ("AI", "ai"), ("voice bot", "ai"), ("AI-Bot", "ai"), ("Human", "human"), ("store", "human"), ("??", None)
])  # fmt: skip
def test_agent_type_normalisation(raw, expected):
    assert sheet_reader.normalise_agent_type(raw) == expected


# ---------------------------------------------------------------------------
# Chunked upload
# ---------------------------------------------------------------------------


def test_chunked_upload_resume_and_assemble(session, monkeypatch):
    monkeypatch.setattr(chunks, "CHUNK_SIZE", 10)
    data = bytes(range(25))
    up = chunks.create_upload(session, "call.mp3", len(data), "audio/mpeg")
    assert chunks.total_chunks(up) == 3

    chunks.write_chunk(up, 2, data[20:], None)
    chunks.write_chunk(up, 0, data[:10], hashlib.sha256(data[:10]).hexdigest())
    assert chunks.received(up) == [0, 2]  # the client resumes by sending only chunk 1

    with pytest.raises(AppError, match="damaged"):
        chunks.write_chunk(up, 1, data[10:20], "0" * 64)
    with pytest.raises(AppError):
        chunks.complete(session, up)  # chunk 1 still missing

    chunks.write_chunk(up, 1, data[10:20], None)
    done = chunks.complete(session, up)
    assert done.sha256 == hashlib.sha256(data).hexdigest()
    assert Path(done.file_path).read_bytes() == data


def test_upload_size_limits(session):
    with pytest.raises(AppError):
        chunks.create_upload(session, "huge.mp3", 10 * 1024**4, "audio/mpeg")


# ---------------------------------------------------------------------------
# Downloader
# ---------------------------------------------------------------------------


def test_share_links_become_direct_links():
    assert "id=ABC123" in direct_link("https://drive.google.com/file/d/ABC123/view?usp=sharing")
    assert direct_link("https://www.dropbox.com/s/xyz/a.mp3?dl=0").endswith("dl=1")


async def test_download_maps_http_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_URLS", "true")
    from app.config import get_settings

    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/missing.mp3":
            return httpx.Response(404)
        if request.url.path == "/page":
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>")
        return httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=b"ID3audio")

    transport = httpx.MockTransport(handler)
    got = await download("http://files.test/ok", tmp_path, transport=transport)
    assert got.path.suffix == ".mp3" and got.size == 8

    with pytest.raises(StageError) as e:
        await download("http://files.test/missing.mp3", tmp_path, transport=transport)
    assert e.value.code == "LINK_NOT_FOUND"
    with pytest.raises(StageError) as e:
        await download("http://files.test/page", tmp_path, transport=transport)
    assert e.value.code == "NOT_AUDIO"


async def test_private_addresses_are_blocked(tmp_path):
    with pytest.raises(StageError) as e:
        await download("http://127.0.0.1/a.mp3", tmp_path)
    assert e.value.code == "LINK_BLOCKED"


def test_dialer_filename_metadata():
    from app.ingest.dialer_filename import parse

    meta = parse(
        "madiha_chougle_thesleepcompany_in__Sales_Outbound__435__-1__9894020300__2026-10-06_20-41-49.mp3"
    )
    assert meta["agent_name"] == "Madiha Chougle"
    assert meta["campaign"] == "Sales Outbound"
    assert meta["phone"] == "9894020300"
    assert meta["call_datetime"].isoformat() == "2026-10-06T20:41:49+05:30"
    assert parse("plain_name.mp3") == {}


def test_quoted_phone_numbers_normalise(session):
    from app.pipeline.leads import normalise_phone

    assert normalise_phone("'+91-9894020300'") == "+919894020300"
    assert normalise_phone("9894020300") == "+919894020300"
    assert normalise_phone("") is None


def test_ameyo_style_rows_are_labelled_by_phone():
    rows = [
        {
            "Phone Number": "'+91-9894020300'",
            "Call Recording URL": "https://x.test/ameyowebaccess/command?command=downloadVoiceLog&data={'id':'1'}",
        }
    ]
    mapping = sheet_reader.suggest_mapping(list(rows[0]), rows)
    assert mapping["recording_url"] == "Call Recording URL" and mapping["lead_phone"] == "Phone Number"
    check = sheet_reader.rows_to_specs(rows, mapping, "human")
    assert check.specs[0].label == "+91-9894020300"


def test_csv_with_single_quotes_in_values(tmp_path):
    """Ameyo export: quoted phones and URLs containing {'…':'…'} must not confuse the CSV reader."""
    p = tmp_path / "export.csv"
    p.write_text(
        "Phone Number,Call Recording URL\n"
        "'+91-9894020300',\"https://x.test:8443/cmd?command=downloadVoiceLog&data={'crtObjectId':'d1','targetFormat':'mp3'}\"\n"
        "'+91-8619162697',\"https://x.test:8443/cmd?command=downloadVoiceLog&data={'crtObjectId':'d2','targetFormat':'mp3'}\"\n"
    )
    headers, rows = sheet_reader.read_table(p)
    assert headers == ["Phone Number", "Call Recording URL"]
    assert rows[0]["Call Recording URL"].endswith("'targetFormat':'mp3'}")
    check = sheet_reader.rows_to_specs(rows, sheet_reader.suggest_mapping(headers, rows), "human")
    assert len(check.specs) == 2 and not check.problems
