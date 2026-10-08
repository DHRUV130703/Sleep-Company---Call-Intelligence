"""OpenAI speech-to-text with speaker labels (gpt-4o-transcribe-diarize).

POST https://api.openai.com/v1/audio/transcriptions (multipart)
    model=gpt-4o-transcribe-diarize, response_format=diarized_json, chunking_strategy=auto
Response: {"segments": [{"speaker": "A", "start": 0.0, "end": 4.2, "text": "..."}, ...]}
Notes: max 25 MB per file; no `prompt`/`language` parameters, so the script setting can't be enforced.
"""

from pathlib import Path

import httpx

from app.contracts import RawSegment, RawTranscript
from app.providers.base import ProviderError, RateLimiter, with_retries

URL = "https://api.openai.com/v1/audio/transcriptions"


class OpenAITranscriber:
    name = "openai"

    def __init__(self, api_key: str, model: str, rpm: int):
        self.api_key = api_key
        self.model = model
        self.limiter = RateLimiter(rpm)

    async def transcribe(self, audio: Path, *, script: str, context: str = "") -> RawTranscript:
        return await with_retries(lambda: self._post(audio), what=f"openai:{self.model}")

    async def _post(self, audio: Path) -> RawTranscript:
        await self.limiter.wait()
        data = {"model": self.model, "response_format": "diarized_json", "chunking_strategy": "auto"}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=20)) as client:
                with audio.open("rb") as f:
                    res = await client.post(
                        URL,
                        data=data,
                        files={"file": (audio.name, f, "audio/mpeg")},
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc}", retryable=True) from exc

        if res.status_code != 200:
            try:
                err = res.json().get("error", {})
            except ValueError:
                err = {}
            msg = err.get("message", res.text[:300])
            code = err.get("code") or err.get("type") or ""
            if code in ("insufficient_quota", "credit_balance_exhausted") or res.status_code in (401, 403):
                raise ProviderError(f"OpenAI: {msg}", no_credits=True)
            if res.status_code == 429 or res.status_code >= 500:
                raise ProviderError(f"OpenAI busy ({res.status_code}): {msg}", retryable=True)
            raise ProviderError(f"OpenAI error {res.status_code}: {msg}")

        segments = res.json().get("segments", [])
        return RawTranscript(
            segments=[
                RawSegment(
                    speaker=str(s.get("speaker", "?")),
                    start=float(s.get("start", 0)),
                    end=float(s.get("end", 0)),
                    text=str(s.get("text", "")).strip(),
                )
                for s in segments
                if str(s.get("text", "")).strip()
            ]
        )
