"""Health, overall stats and settings endpoints."""

import json
import shutil
import subprocess
import time

import httpx
from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy import func, inspect, text
from sqlmodel import Session, select

from app import __version__, storage
from app.config import Settings, get_business, get_settings, reload_business
from app.db import get_engine, get_session, utcnow
from app.errors import AppError, ErrorCode
from app.models import Call, CallStatus
from app.schemas import HealthCheck, HealthResponse, ProviderInfo, SettingsResponse, StatsResponse
from app.worker import last_heartbeat

router = APIRouter(tags=["settings"])

WORKER_ALIVE_WITHIN_S = 20


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def _check_database() -> HealthCheck:
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        if not inspect(engine).has_table("alembic_version"):
            return HealthCheck(
                name="database", label="Database", state="fail", detail="Not set up yet. Run: make migrate"
            )
        where = (
            "SQLite file on this computer"
            if engine.dialect.name == "sqlite"
            else f"{engine.dialect.name} (cloud)"
        )
        return HealthCheck(
            name="database", label="Database", state="ok", detail=f"Connected and migrated — {where}"
        )
    except Exception as exc:
        return HealthCheck(name="database", label="Database", state="fail", detail=str(exc)[:200])


def _check_binary(name: str) -> HealthCheck:
    path = shutil.which(name)
    if not path:
        return HealthCheck(
            name=name,
            label=name,
            state="fail",
            detail=f"{name} not found. Install it (macOS: brew install ffmpeg)",
        )
    try:
        first_line = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=5).stdout
        version = first_line.splitlines()[0].split(" Copyright")[0] if first_line else path
    except Exception:
        version = path
    return HealthCheck(name=name, label=name, state="ok", detail=version)


def _check_worker() -> HealthCheck:
    try:
        beat = last_heartbeat()
    except Exception as exc:
        return HealthCheck(name="worker", label="Worker", state="fail", detail=str(exc)[:200])
    if beat is None:
        return HealthCheck(
            name="worker",
            label="Worker",
            state="fail",
            detail="Not running. Start it with: make worker (make dev starts it too)",
        )
    age = (utcnow() - beat).total_seconds()
    if age > WORKER_ALIVE_WITHIN_S:
        return HealthCheck(
            name="worker",
            label="Worker",
            state="fail",
            detail=f"No heartbeat for {int(age)}s. Is it running?",
        )
    return HealthCheck(
        name="worker", label="Worker", state="ok", detail=f"Running (heartbeat {int(age)}s ago)"
    )


def _provider_key_present(provider: str, s: Settings) -> bool:
    return {
        "assemblyai": bool(s.assemblyai_api_key),
        "groq": bool(s.groq_api_key),
        "openai": bool(s.openai_api_key),
        "gemini": bool(s.gemini_api_key),
        "faster_whisper": True,
        "mlx_whisper": True,
        "claude_cli": True,
        "ollama": True,
        "fake": True,
    }.get(provider, False)


_claude_status: tuple[float, HealthCheck] | None = None


def _check_claude_cli(s: Settings) -> HealthCheck:
    """`claude auth status` (cached for a minute — health is polled often)."""
    global _claude_status
    if _claude_status and time.monotonic() - _claude_status[0] < 60:
        return _claude_status[1]
    path = shutil.which(s.claude_cli_path)
    if not path:
        check = HealthCheck(
            name="analyzer",
            label="Analysis (Claude)",
            state="fail",
            detail="The `claude` command isn't installed. Install Claude Code, then run: claude auth login",
        )
    else:
        try:
            out = subprocess.run([path, "auth", "status"], capture_output=True, text=True, timeout=15).stdout
            logged_in = bool(json.loads(out or "{}").get("loggedIn"))
        except (OSError, ValueError, subprocess.TimeoutExpired):
            logged_in = False
        check = HealthCheck(
            name="analyzer",
            label="Analysis (Claude)",
            state="ok" if logged_in else "fail",
            detail=f"Claude ({s.analysis_model}) — logged in"
            if logged_in
            else "Claude isn't logged in. In a terminal run: claude auth login",
        )
    _claude_status = (time.monotonic(), check)
    return check


def _check_ollama(s: Settings) -> HealthCheck:
    label = "Analysis (Ollama)"
    try:
        res = httpx.get(f"{s.ollama_url.rstrip('/')}/api/tags", timeout=3)
        models = {m["name"] for m in res.json().get("models", [])}
    except (httpx.HTTPError, ValueError):
        return HealthCheck(
            name="analyzer",
            label=label,
            state="fail",
            detail="Ollama isn't running. Open the Ollama app (or run: ollama serve)",
        )
    wanted = {s.analysis_model, s.lead_summary_model}
    missing = [m for m in wanted if m not in models and f"{m}:latest" not in models]
    if missing:
        return HealthCheck(
            name="analyzer",
            label=label,
            state="fail",
            detail=f"Model not downloaded. Run: ollama pull {missing[0]}",
        )
    return HealthCheck(
        name="analyzer", label=label, state="ok", detail=f"Ollama ({s.analysis_model}) — ready"
    )


def _check_whisper(s: Settings, provider: str) -> HealthCheck:
    module, model = (
        ("faster_whisper", s.whisper_model)
        if provider == "faster_whisper"
        else ("mlx_whisper", s.mlx_whisper_model)
    )
    label = f"Transcription ({provider.replace('_', '-')})"
    try:
        __import__(module)
    except ImportError:
        return HealthCheck(
            name="transcriber", label=label, state="fail", detail=f"{module} isn't installed. Run: make setup"
        )
    return HealthCheck(
        name="transcriber", label=label, state="ok", detail=f"Local Whisper ({model}) on this Mac"
    )


def _check_provider(kind: str, provider: str, s: Settings) -> HealthCheck:
    if provider == "ollama":
        return _check_ollama(s)
    if provider == "claude_cli":
        return _check_claude_cli(s)
    if provider in ("faster_whisper", "mlx_whisper"):
        return _check_whisper(s, provider)
    label = "Transcription" if kind == "transcriber" else "Analysis"
    if _provider_key_present(provider, s):
        return HealthCheck(name=kind, label=label, state="ok", detail=f"{provider} — ready")
    key_name = f"{provider.upper()}_API_KEY"
    return HealthCheck(
        name=kind, label=label, state="warn", detail=f"{provider} selected but {key_name} is empty in .env"
    )


def _check_config() -> HealthCheck:
    try:
        b = get_business()
        return HealthCheck(
            name="config",
            label="Config files",
            state="ok",
            detail=f"{len(b.scorecard.dimensions)} scorecard dimensions, "
            f"{len(b.intent.buckets)} intent buckets",
        )
    except (ValidationError, OSError, ValueError) as exc:
        return HealthCheck(name="config", label="Config files", state="fail", detail=str(exc)[:300])


def _check_storage() -> HealthCheck:
    """Recordings, uploads and spreadsheets are stored in the database (app/storage.py)."""
    try:
        n, size = storage.total_size()
    except Exception as exc:
        return HealthCheck(name="storage", label="Storage", state="fail", detail=str(exc)[:200])
    return HealthCheck(
        name="storage", label="Storage", state="ok", detail=f"{n} files, {size / 1e6:.0f} MB in the database"
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    s = get_settings()
    checks = [
        _check_database(),
        _check_worker(),
        _check_binary("ffmpeg"),
        _check_binary("ffprobe"),
        _check_provider("transcriber", s.transcriber, s),
        _check_provider("analyzer", s.analyzer, s),
        _check_config(),
        _check_storage(),
    ]
    status = "fail" if any(c.state == "fail" for c in checks) else "ok"
    return HealthResponse(status=status, version=__version__, checks=checks)


# ---------------------------------------------------------------------------
# Stats (sidebar footer)
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=StatsResponse)
def stats(session: Session = Depends(get_session)) -> StatsResponse:
    total = session.exec(select(func.count()).select_from(Call)).one()
    done_filter = Call.status == CallStatus.done
    analysed = session.exec(select(func.count()).select_from(Call).where(done_filter)).one()
    seconds = session.exec(select(func.coalesce(func.sum(Call.duration_s), 0)).where(done_filter)).one()
    last = session.exec(select(func.max(Call.updated_at)).where(done_filter)).one()
    return StatsResponse(
        total_calls=total, analysed_calls=analysed, audio_seconds=float(seconds or 0), last_processed_at=last
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def _settings_response() -> SettingsResponse:
    s = get_settings()
    b = get_business()
    transcribe_model = {
        "openai": s.openai_transcribe_model,
        "gemini": s.gemini_transcribe_model,
        "assemblyai": s.assemblyai_models.split(",")[0],
        "faster_whisper": s.whisper_model,
        "mlx_whisper": s.mlx_whisper_model,
    }.get(s.transcriber, s.transcriber)
    return SettingsResponse(
        transcriber=ProviderInfo(
            selected=s.transcriber,
            model=transcribe_model or "(not set)",
            key_present=_provider_key_present(s.transcriber, s),
        ),
        analyzer=ProviderInfo(
            selected=s.analyzer, model=s.analysis_model, key_present=_provider_key_present(s.analyzer, s)
        ),
        default_transcript_script=s.default_transcript_script,
        concurrency={
            "download": s.concurrency_download,
            "transcribe": s.concurrency_transcribe,
            "analyze": s.concurrency_analyze,
        },
        limits={
            "max_file_gb": s.max_file_gb,
            "max_zip_gb": s.max_zip_gb,
            "max_calls_per_batch": s.max_calls_per_batch,
            "max_recording_hours": s.max_recording_hours,
        },
        mask_phones=s.mask_phones,
        raw_audio_retention_days=s.raw_audio_retention_days,
        timezone=s.default_timezone,
        passcode_enabled=bool(s.app_passcode),
        scorecard=b.scorecard,
        intent=b.intent,
    )


@router.get("/settings", response_model=SettingsResponse)
def read_settings() -> SettingsResponse:
    return _settings_response()


@router.post("/settings/reload-config", response_model=SettingsResponse)
def reload_config() -> SettingsResponse:
    try:
        reload_business()
    except (ValidationError, OSError, ValueError) as exc:
        raise AppError(ErrorCode.CONFIG_INVALID, detail={"reason": str(exc)[:1000]}) from exc
    return _settings_response()
