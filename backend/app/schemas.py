"""API response/request shapes. LLM output contracts (PRD §7.1) are added here in M3."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.config import IntentRubric, Scorecard

CheckState = Literal["ok", "warn", "fail"]


class HealthCheck(BaseModel):
    name: str
    label: str
    state: CheckState
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok", "fail"]  # "fail" if any check fails; warnings don't fail health
    version: str
    checks: list[HealthCheck]


class StatsResponse(BaseModel):
    total_calls: int
    analysed_calls: int
    audio_seconds: float
    last_processed_at: datetime | None


class ProviderInfo(BaseModel):
    selected: str
    model: str
    key_present: bool


class SettingsResponse(BaseModel):
    transcriber: ProviderInfo
    analyzer: ProviderInfo
    default_transcript_script: str
    concurrency: dict[str, int]
    limits: dict[str, float]
    mask_phones: bool
    raw_audio_retention_days: int
    timezone: str
    passcode_enabled: bool
    scorecard: Scorecard
    intent: IntentRubric
