"""Google Gemini: structured JSON generation (analysis) and audio transcription.

REST API: POST {BASE}/models/{model}:generateContent with
    generationConfig.responseMimeType = "application/json"
    generationConfig.responseJsonSchema = <JSON schema>
Audio is sent inline (base64). Long calls are split into chunks before they reach here,
so each request stays far below the inline size limit.
"""

import base64
import json
import logging
import re
import time
from functools import partial
from pathlib import Path
from typing import Any

import httpx

from app.contracts import RawTranscript, json_schema_for
from app.prompts import render
from app.providers.base import ProviderError, RateLimiter, with_retries

log = logging.getLogger("providers")

BASE = "https://generativelanguage.googleapis.com/v1beta"
SKIP_EXHAUSTED_S = 3600  # daily quota used up → don't retry this model for an hour
SKIP_OVERLOADED_S = 120  # "high demand" → give it two minutes
MIME = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
}


def _retry_after(body: dict[str, Any]) -> float | None:
    """Gemini puts the suggested wait in error.details[].retryDelay, e.g. "17s"."""
    for d in body.get("error", {}).get("details", []):
        if m := re.fullmatch(r"([\d.]+)s", str(d.get("retryDelay", ""))):
            return float(m.group(1))
    return None


def _is_daily_quota(body: dict[str, Any]) -> bool:
    """Per-minute limits clear by themselves; per-day limits (or no billing) don't until tomorrow.

    Gemini uses the same message for both, so look at the quota id in error.details[].violations[].
    """
    for d in body.get("error", {}).get("details", []):
        for v in d.get("violations", []):
            if "PerDay" in str(v.get("quotaId", "")):
                return True
    return "per day" in body.get("error", {}).get("message", "").lower()


class GeminiClient:
    name = "gemini"

    def __init__(self, api_key: str, rpm: int, fallback_models: list[str]):
        self.api_key = api_key
        self.fallback_models = fallback_models
        self.limiter = RateLimiter(rpm)
        self._skip_until: dict[str, float] = {}  # model → time when it may be tried again

    async def json(
        self, *, prompt: str, schema: dict[str, Any], model: str, audio: Path | None = None
    ) -> dict[str, Any]:
        parts: list[dict[str, Any]] = [{"text": prompt}]
        if audio is not None:
            data = base64.b64encode(audio.read_bytes()).decode()
            parts.append({"inline_data": {"mime_type": MIME.get(audio.suffix, "audio/mpeg"), "data": data}})
        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
                "temperature": 0.2,
            },
        }

        # Try the chosen model, then each fallback. A model that is out of daily quota (or keeps being
        # overloaded) is skipped for a while so later calls don't waste time on it.
        chain = [model] + [m for m in self.fallback_models if m != model]
        last: ProviderError | None = None
        for m in chain:
            if time.monotonic() < self._skip_until.get(m, 0):
                continue
            try:
                return await with_retries(partial(self._post, m, body), what=f"gemini:{m}", max_attempts=3)
            except ProviderError as exc:
                last = exc
                if exc.no_credits:
                    self._skip_until[m] = time.monotonic() + SKIP_EXHAUSTED_S
                elif exc.retryable:
                    self._skip_until[m] = time.monotonic() + SKIP_OVERLOADED_S
                else:
                    raise  # a real error (bad request) — another model won't fix it
                log.warning(
                    "gemini model unavailable; trying next", extra={"model": m, "reason": str(exc)[:160]}
                )
        raise last or ProviderError(
            "Every Gemini model is out of quota. Enable billing or wait.", no_credits=True
        )

    async def _post(self, model: str, body: dict[str, Any]) -> dict[str, Any]:
        await self.limiter.wait()
        url = f"{BASE}/models/{model}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=20)) as client:
                res = await client.post(url, json=body, headers={"x-goog-api-key": self.api_key})
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc}", retryable=True) from exc

        if res.status_code != 200:
            try:
                err = res.json()
            except ValueError:
                err = {}
            msg = err.get("error", {}).get("message", res.text[:300])
            if res.status_code == 429:
                daily = _is_daily_quota(err)
                raise ProviderError(
                    f"Gemini {'daily' if daily else 'per-minute'} quota reached: {msg[:120]}",
                    retryable=not daily,
                    no_credits=daily,
                    retry_after=_retry_after(err) or 30,
                )
            if res.status_code in (500, 502, 503, 504):
                raise ProviderError(f"Gemini busy ({res.status_code}): {msg}", retryable=True)
            if res.status_code in (401, 403):
                raise ProviderError(f"Gemini key rejected: {msg}", no_credits=True)
            raise ProviderError(f"Gemini error {res.status_code}: {msg}")

        data = res.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
            return json.loads(text)  # type: ignore[no-any-return]
        except (KeyError, IndexError, ValueError) as exc:
            reason = data.get("candidates", [{}])[0].get("finishReason", "unknown")
            raise ProviderError(f"Gemini returned no usable JSON (finish: {reason})", retryable=True) from exc


SCRIPT_RULES = {
    "roman": "Write Hindi or other Indian-language speech in Roman letters (Hinglish), e.g. 'Haan, kal aa sakta hoon'. "
    "Keep English words in English.",
    "devanagari": "Write Hindi speech in Devanagari script. Keep English words in English (Latin letters).",
    "english": "Translate everything into natural English.",
}


class GeminiTranscriber:
    name = "gemini"

    def __init__(self, client: GeminiClient, model: str):
        self.client = client
        self.model = model

    async def transcribe(self, audio: Path, *, script: str, context: str = "") -> RawTranscript:
        prompt, _ = render(
            "transcribe",
            script_rule=SCRIPT_RULES.get(script, SCRIPT_RULES["roman"]),
            context=f"The previous part of this call ended with:\n{context}\nKeep the same speaker labels."
            if context
            else "",
        )
        data = await self.client.json(
            prompt=prompt, schema=json_schema_for(RawTranscript), model=self.model, audio=audio
        )
        return RawTranscript.model_validate(data)
