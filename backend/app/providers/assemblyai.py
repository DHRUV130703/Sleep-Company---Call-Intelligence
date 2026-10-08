"""AssemblyAI speech-to-text (cloud). Recordings are uploaded to AssemblyAI for transcription.

Why: Universal-3.5 Pro handles Hindi↔English switching inside a sentence natively and labels speakers
(A, B) itself — exactly what Hinglish sales calls need. Free tier: ~185 hours of recorded audio.

Flow (REST, https://api.assemblyai.com, header `authorization: <key>`):
    1. POST /v2/upload            (raw audio bytes)          → {"upload_url"}
    2. POST /v2/transcript        {audio_url, speech_models, …} → {"id", "status"}
    3. GET  /v2/transcript/{id}   until status is "completed" or "error"
    → "utterances": [{"speaker": "A", "start": ms, "end": ms, "text"}]
Speaker A/B are then mapped to agent/customer by the analysis model (pipeline/analysis.py: map_roles).
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from app.contracts import RawSegment, RawTranscript
from app.providers.base import ProviderError, RateLimiter, with_retries

log = logging.getLogger("providers")

BASE = "https://api.assemblyai.com"
POLL_EVERY_S = 3
MAX_WAIT_S = 30 * 60

# Brand and product words, so they are spelled right (AssemblyAI "keyterms_prompt").
KEYTERMS = [
    "The Sleep Company", "SmartGRID", "Ortho Pro", "Smart Ortho", "Elite", "Luxe", "mattress", "pillow",
    "recliner", "sofa", "EMI", "store visit", "HiLITE Mall", "offer price", "MRP", "warranty",
]  # fmt: skip


class AssemblyAITranscriber:
    name = "assemblyai"

    def __init__(
        self,
        api_key: str,
        models: list[str],
        rpm: int = 60,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key
        self.transport = transport  # tests pass a fake server here
        self.models = models
        self.model = models[0] if models else ""
        self.limiter = RateLimiter(rpm)

    async def transcribe(self, audio: Path, *, script: str, context: str = "") -> RawTranscript:
        async with httpx.AsyncClient(
            base_url=BASE,
            headers={"authorization": self.api_key},
            timeout=httpx.Timeout(300, connect=20),
            transport=self.transport,
        ) as client:
            upload_url = await with_retries(lambda: self._upload(client, audio), what="assemblyai:upload")
            job_id = await with_retries(lambda: self._submit(client, upload_url), what="assemblyai:submit")
            data = await self._wait(client, job_id)

        utterances = data.get("utterances") or []
        if not utterances and data.get("text"):  # no speaker turns returned → one block
            utterances = [
                {
                    "speaker": "?",
                    "start": 0,
                    "end": int((data.get("audio_duration") or 0) * 1000),
                    "text": data["text"],
                }
            ]
        log.info(
            "assemblyai transcript",
            extra={
                "id": job_id,
                "model": data.get("speech_model_used") or data.get("speech_model"),
                "turns": len(utterances),
                "language": data.get("language_code"),
            },
        )
        return RawTranscript(
            segments=[
                RawSegment(
                    speaker=str(u.get("speaker") or "?"),
                    start=round(u.get("start", 0) / 1000, 2),
                    end=round(u.get("end", 0) / 1000, 2),
                    text=str(u.get("text", "")).strip(),
                )
                for u in utterances
                if str(u.get("text", "")).strip()
            ]
        )

    # -- steps ---------------------------------------------------------------

    async def _upload(self, client: httpx.AsyncClient, audio: Path) -> str:
        await self.limiter.wait()
        try:
            res = await client.post(
                "/v2/upload", content=audio.read_bytes(), headers={"content-type": "application/octet-stream"}
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc}", retryable=True) from exc
        _raise_for(res)
        return str(res.json()["upload_url"])

    async def _submit(self, client: httpx.AsyncClient, audio_url: str) -> str:
        await self.limiter.wait()
        body: dict[str, Any] = {
            "audio_url": audio_url,
            "speech_models": self.models,  # first available is used, e.g. universal-3-5-pro then universal-2
            "language_detection": True,  # Hindi, English and code-switching between them
            "speaker_labels": True,
            "speakers_expected": 2,  # agent + customer
            "keyterms_prompt": KEYTERMS,
        }
        try:
            res = await client.post("/v2/transcript", json=body)
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc}", retryable=True) from exc
        _raise_for(res)
        return str(res.json()["id"])

    async def _wait(self, client: httpx.AsyncClient, job_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + MAX_WAIT_S
        while time.monotonic() < deadline:
            try:
                res = await client.get(f"/v2/transcript/{job_id}")
            except httpx.HTTPError:
                await asyncio.sleep(POLL_EVERY_S)  # a blip while polling: just try again
                continue
            _raise_for(res)
            data: dict[str, Any] = res.json()
            if data.get("status") == "completed":
                return data
            if data.get("status") == "error":
                msg = str(data.get("error") or "unknown error")
                low = msg.lower()
                if "balance" in low or "credit" in low or "payment" in low:
                    raise ProviderError(f"AssemblyAI: {msg}", no_credits=True)
                if "no spoken audio" in low or "no speech" in low:
                    return {"utterances": []}  # the pipeline marks the call as silent
                raise ProviderError(f"AssemblyAI couldn't transcribe this call: {msg}")
            await asyncio.sleep(POLL_EVERY_S)
        raise ProviderError("AssemblyAI took too long", retryable=True)


def _raise_for(res: httpx.Response) -> None:
    if res.status_code < 400:
        return
    try:
        msg = str(res.json().get("error") or res.text[:200])
    except ValueError:
        msg = res.text[:200]
    if res.status_code in (401, 403):
        raise ProviderError(f"AssemblyAI rejected the API key: {msg}", no_credits=True)
    if res.status_code == 402:
        raise ProviderError(f"AssemblyAI account has no credit left: {msg}", no_credits=True)
    if res.status_code == 429 or res.status_code >= 500:
        raise ProviderError(f"AssemblyAI busy ({res.status_code}): {msg}", retryable=True)
    raise ProviderError(f"AssemblyAI error {res.status_code}: {msg}")
