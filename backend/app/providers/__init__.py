"""Pick providers from settings. The rest of the app only uses get_transcriber() and get_llm().

Fallback: if the main transcriber's account is out of credits (or it's down after retries), the
fallback transcriber (TRANSCRIBER_FALLBACK) is used. After a "no credits" error, the main one is
skipped for 10 minutes so every call doesn't waste a request.
"""

import logging
import time
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.contracts import RawTranscript
from app.errors import AppError, ErrorCode
from app.providers.assemblyai import AssemblyAITranscriber
from app.providers.base import LLM, ProviderError, Transcriber
from app.providers.claude_cli import ClaudeCLI
from app.providers.fake import FakeLLM, FakeTranscriber
from app.providers.faster_whisper_local import FasterWhisperTranscriber
from app.providers.gemini import GeminiClient, GeminiTranscriber
from app.providers.groq import GroqClient
from app.providers.ollama import OllamaClient
from app.providers.openai_transcriber import OpenAITranscriber
from app.providers.whisper_local import LocalWhisperTranscriber

log = logging.getLogger("providers")
SKIP_AFTER_NO_CREDITS_S = 600


@lru_cache
def _gemini_client() -> GeminiClient:
    s = get_settings()
    if not s.gemini_api_key:
        raise AppError(ErrorCode.PROVIDER_NOT_CONFIGURED, detail={"key": "GEMINI_API_KEY"})
    fallbacks = [m.strip() for m in s.gemini_fallback_models.split(",") if m.strip()]
    return GeminiClient(s.gemini_api_key, s.gemini_rpm, fallbacks)


def _build_transcriber(name: str) -> Transcriber:
    s = get_settings()
    if name == "fake":
        return FakeTranscriber()
    if name == "assemblyai":
        if not s.assemblyai_api_key:
            raise AppError(ErrorCode.PROVIDER_NOT_CONFIGURED, detail={"key": "ASSEMBLYAI_API_KEY"})
        models = [m.strip() for m in s.assemblyai_models.split(",") if m.strip()]
        return AssemblyAITranscriber(s.assemblyai_api_key, models)
    if name == "faster_whisper":
        return FasterWhisperTranscriber(s.whisper_model, s.whisper_compute_type)
    if name == "mlx_whisper":
        return LocalWhisperTranscriber(s.mlx_whisper_model)
    if name == "gemini":
        return GeminiTranscriber(_gemini_client(), s.gemini_transcribe_model)
    if name == "openai":
        if not s.openai_api_key:
            raise AppError(ErrorCode.PROVIDER_NOT_CONFIGURED, detail={"key": "OPENAI_API_KEY"})
        return OpenAITranscriber(s.openai_api_key, s.openai_transcribe_model, s.openai_rpm)
    raise ValueError(f"unknown transcriber {name!r}")


class TranscriberWithFallback:
    def __init__(self, primary: str, fallback: str | None):
        self.primary_name = primary
        self.fallback_name = fallback
        self._primary_blocked_until = 0.0
        self.last_used: Transcriber | None = None  # which one produced the last transcript

    @property
    def name(self) -> str:
        return self.primary_name

    async def transcribe(self, audio: Path, *, script: str, context: str = "") -> RawTranscript:
        if time.monotonic() >= self._primary_blocked_until:
            try:
                primary = _build_transcriber(self.primary_name)
                self.last_used = primary
                return await primary.transcribe(audio, script=script, context=context)
            except (ProviderError, AppError) as exc:
                if not self.fallback_name:
                    if isinstance(exc, AppError):  # e.g. no API key in .env → a clear, non-retried error
                        key = exc.detail.get("key", "the API key")
                        raise ProviderError(
                            f"{key} is empty in .env. Add it, restart the app, then click Retry.",
                            no_credits=True,
                        ) from exc
                    raise
                # Out of credits / no key → don't even try the main one for a while.
                if isinstance(exc, AppError) or exc.no_credits:
                    self._primary_blocked_until = time.monotonic() + SKIP_AFTER_NO_CREDITS_S
                log.warning(
                    "main transcriber failed; using fallback",
                    extra={
                        "primary": self.primary_name,
                        "fallback": self.fallback_name,
                        "reason": str(exc)[:200],
                    },
                )
        if not self.fallback_name:
            raise ProviderError(f"{self.primary_name} is unavailable and no fallback is set", no_credits=True)
        fallback = _build_transcriber(self.fallback_name)
        self.last_used = fallback
        return await fallback.transcribe(audio, script=script, context=context)


@lru_cache
def get_transcriber() -> TranscriberWithFallback:
    s = get_settings()
    fallback = (
        None
        if s.transcriber_fallback == "none" or s.transcriber_fallback == s.transcriber
        else (s.transcriber_fallback)
    )
    return TranscriberWithFallback(s.transcriber, fallback)


@lru_cache
def get_llm() -> LLM:
    s = get_settings()
    if s.analyzer == "fake":
        return FakeLLM()
    if s.analyzer == "groq":
        if not s.groq_api_key:
            raise AppError(ErrorCode.PROVIDER_NOT_CONFIGURED, detail={"key": "GROQ_API_KEY"})
        return GroqClient(s.groq_api_key, s.groq_rpm, s.groq_reasoning_effort)
    if s.analyzer == "ollama":
        return OllamaClient(s.ollama_url, s.ollama_concurrency, s.ollama_context_tokens)
    if s.analyzer == "claude_cli":
        return ClaudeCLI(s.claude_cli_path, s.claude_concurrency, s.data_dir / "claude-work")
    return _gemini_client()


def reset_providers() -> None:
    """Forget cached providers (after settings change, and in tests)."""
    _gemini_client.cache_clear()
    get_transcriber.cache_clear()
    get_llm.cache_clear()
