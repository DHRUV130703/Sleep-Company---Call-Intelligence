"""App settings (from .env) and business rules (from config/*.yaml).

- `get_settings()`   → machine settings and secrets. Edit `.env` (see `.env.example`).
- `get_business()`   → scorecard, intent buckets, objection types… Edit `config/*.yaml`,
                       then click "Reload config" in Settings (or restart).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # LimeZip/
CONFIG_DIR = PROJECT_ROOT / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    # Providers
    assemblyai_api_key: str = ""
    # Tried in order; the first one available on your account is used.
    assemblyai_models: str = "universal-3-5-pro,universal-2"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    # Default: all cloud — AssemblyAI for speech-to-text (Hinglish + speaker labels), Groq for the insights.
    transcriber: Literal["assemblyai", "faster_whisper", "mlx_whisper", "openai", "gemini", "fake"] = (
        "assemblyai"
    )
    transcriber_fallback: Literal["gemini", "openai", "none"] = "none"  # used if the main one is unavailable
    analyzer: Literal["groq", "ollama", "claude_cli", "gemini", "fake"] = "groq"
    groq_api_key: str = ""
    groq_rpm: int = 30  # requests per minute (raise if your Groq plan allows more)
    groq_reasoning_effort: Literal["none", "low", "medium", "high"] = "low"  # how much the model thinks first
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_concurrency: int = 1  # requests at the same time (one local model → keep at 1–2)
    ollama_context_tokens: int = 16384  # enough for a ~20-minute call transcript
    whisper_model: str = "large-v3-turbo"  # faster-whisper model name
    whisper_compute_type: str = "int8"  # faster-whisper on CPU: int8 is fastest
    mlx_whisper_model: str = "mlx-community/whisper-large-v3-turbo"  # only for TRANSCRIBER=mlx_whisper
    claude_cli_path: str = "claude"
    claude_concurrency: int = 2  # Claude requests running at the same time
    openai_transcribe_model: str = "gpt-4o-transcribe-diarize"  # labels speakers; whisper-1 does not
    gemini_transcribe_model: str = "gemini-2.5-flash"
    analysis_model: str = (
        "qwen3:8b"  # model for the analyzer (Ollama: qwen3:8b; Claude: sonnet; Gemini: gemini-…)
    )
    lead_summary_model: str = "qwen/qwen3.8-27b"  # model for small jobs
    # Tried in order when the chosen Gemini model is overloaded or out of its daily quota.
    gemini_fallback_models: str = "gemini-3.1-flash-lite,gemini-flash-lite-latest,gemini-2.5-flash"
    gemini_rpm: int = 5  # requests per minute; raise it if your Gemini plan allows more
    openai_rpm: int = 50

    # Storage
    data_dir: Path = Path("data")
    database_url: str = ""  # empty → sqlite file inside data_dir

    # Processing
    concurrency_download: int = 4
    concurrency_transcribe: int = 3
    concurrency_analyze: int = 4
    default_transcript_script: Literal["roman", "devanagari", "english"] = "roman"
    stereo_left_is: Literal["agent", "customer"] = "agent"
    chunk_minutes: int = 10  # long recordings are transcribed in pieces of this length
    allow_private_urls: bool = False  # true only to test links served from this machine

    # Limits
    max_file_gb: float = 2
    max_zip_gb: float = 5
    max_calls_per_batch: int = 2000
    max_recording_hours: float = 3

    # Locale & privacy
    default_timezone: str = "Asia/Kolkata"
    default_country: str = "IN"
    mask_phones: bool = True
    raw_audio_retention_days: int = 30
    app_passcode: str = ""

    # Server (the API port is fixed at 8000 — see Makefile and frontend/vite.config.ts)
    frontend_origin: str = "http://localhost:5173"
    # Base of the public report links stored with each saved report. Empty = frontend_origin (works on this
    # computer only); set it to the app's public address once it is deployed.
    public_base_url: str = ""

    @field_validator("data_dir")
    @classmethod
    def _resolve_data_dir(cls, v: Path) -> Path:
        # Relative paths are relative to the project root, not to wherever the process started.
        return v if v.is_absolute() else (PROJECT_ROOT / v).resolve()

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'app.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------------------
# Business rules (config/*.yaml)
# ---------------------------------------------------------------------------


class ScoreDimension(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    guide: str = ""


class Scorecard(BaseModel):
    dimensions: list[ScoreDimension]
    quality_score: str = "mean_of_dimensions_as_percent"

    @field_validator("dimensions")
    @classmethod
    def _unique_keys(cls, dims: list[ScoreDimension]) -> list[ScoreDimension]:
        keys = [d.key for d in dims]
        if len(keys) != len(set(keys)):
            raise ValueError("scorecard dimension keys must be unique")
        if not dims:
            raise ValueError("scorecard needs at least one dimension")
        return dims


class IntentSignals(BaseModel):
    positive: list[str] = []
    negative: list[str] = []


class IntentRubric(BaseModel):
    buckets: dict[str, tuple[int, int]]
    special: dict[str, str] = {}
    signals: IntentSignals = IntentSignals()
    objection_types: list[str]
    ai_failure_patterns: list[str]

    @model_validator(mode="after")
    def _buckets_cover_0_to_100(self) -> "IntentRubric":
        covered: set[int] = set()
        for name, (lo, hi) in self.buckets.items():
            if lo > hi:
                raise ValueError(f"intent bucket '{name}': {lo} > {hi}")
            span = set(range(lo, hi + 1))
            if covered & span:
                raise ValueError(f"intent bucket '{name}' overlaps another bucket")
            covered |= span
        if covered != set(range(0, 101)):
            raise ValueError("intent buckets must cover every score from 0 to 100 exactly once")
        return self

    def bucket_for(self, score: int) -> str:
        for name, (lo, hi) in self.buckets.items():
            if lo <= score <= hi:
                return name
        raise ValueError(f"score {score} is outside 0–100")


class Product(BaseModel):
    name: str
    category: str = ""
    pitch_when: str = ""


class ProductCatalog(BaseModel):
    products: list[Product] = []


class PlaybookEntry(BaseModel):
    label: str = ""
    area: str = ""
    fix: str = ""


class PriorityRule(BaseModel):
    gap: float
    weak_share: float


class PriorityRules(BaseModel):
    high: PriorityRule = PriorityRule(gap=1.0, weak_share=60)
    medium: PriorityRule = PriorityRule(gap=0.5, weak_share=30)


class BotPlaybook(BaseModel):
    """How the AI vs Human page ranks what to fix in the bot (config/bot_playbook.yaml)."""

    priority: PriorityRules = PriorityRules()
    weak_score: int = 2
    on_par_margin: float = 0.3
    outcome_margin: float = 10
    target_score: float = 4.0
    dimensions: dict[str, PlaybookEntry] = {}
    failure_patterns: dict[str, PlaybookEntry] = {}


class BusinessConfig(BaseModel):
    scorecard: Scorecard
    intent: IntentRubric
    catalog: ProductCatalog = ProductCatalog()
    playbook: BotPlaybook = BotPlaybook()


def load_business_config(config_dir: Path = CONFIG_DIR) -> BusinessConfig:
    """Read and validate the YAML files. Raises a clear error if a file is wrong."""

    def read(name: str, required: bool = True) -> dict:
        path = config_dir / name
        if not required and not path.exists():
            return {}
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    return BusinessConfig(
        scorecard=Scorecard.model_validate(read("scorecard.yaml")),
        intent=IntentRubric.model_validate(read("intent_rubric.yaml")),
        catalog=ProductCatalog.model_validate(read("products.yaml", required=False)),
        playbook=BotPlaybook.model_validate(read("bot_playbook.yaml", required=False)),
    )


_business: BusinessConfig | None = None


def get_business() -> BusinessConfig:
    global _business
    if _business is None:
        _business = load_business_config()
    return _business


def reload_business() -> BusinessConfig:
    """Re-read the YAML files (used by Settings → Reload config)."""
    global _business
    _business = load_business_config()
    return _business
