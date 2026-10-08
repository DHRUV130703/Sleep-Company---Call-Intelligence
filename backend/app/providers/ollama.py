"""Local LLM with Ollama — runs on this Mac, no key, nothing leaves the machine.

Setup (once):   install Ollama (ollama.com), open it, then:   ollama pull qwen3:8b
API: POST {OLLAMA_URL}/api/chat with "format": <JSON schema> (Ollama forces the answer to match it)
and "think": false (skip the model's hidden reasoning — faster, and the schema already guides it).
Ollama can't listen to audio, so transcription is done by Whisper.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.providers.base import ProviderError, with_retries

log = logging.getLogger("providers")

SYSTEM_PROMPT = (
    "You are a precise analyst of sales phone calls for The Sleep Company (India). "
    "Reply with JSON only, matching the requested format, and follow the user's rules exactly."
)


class OllamaClient:
    name = "ollama"

    def __init__(self, base_url: str, concurrency: int, context_tokens: int):
        self.base_url = base_url.rstrip("/")
        self.context_tokens = context_tokens
        self._slots = asyncio.Semaphore(max(1, concurrency))  # one model on one GPU: keep this small

    async def json(
        self, *, prompt: str, schema: dict[str, Any], model: str, audio: Path | None = None
    ) -> dict[str, Any]:
        if audio is not None:
            raise ProviderError("Ollama can't process audio; use Whisper for transcription")
        return await with_retries(
            lambda: self._chat(prompt, schema, model), what=f"ollama:{model}", max_attempts=3
        )

    async def _chat(self, prompt: str, schema: dict[str, Any], model: str) -> dict[str, Any]:
        body = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            "format": schema,
            "stream": False,
            "think": False,
            "keep_alive": "30m",  # keep the model loaded between calls
            "options": {"temperature": 0.2, "num_ctx": self.context_tokens},
        }
        async with self._slots:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(900, connect=10)) as client:
                    res = await client.post(f"{self.base_url}/api/chat", json=body)
            except httpx.ConnectError as exc:
                raise ProviderError(
                    "Ollama isn't running. Open the Ollama app (or run: ollama serve), then click Retry.",
                    no_credits=True,
                ) from exc
            except httpx.TimeoutException as exc:
                raise ProviderError("Ollama took too long to answer", retryable=True) from exc

        if res.status_code == 404:
            raise ProviderError(
                f"The model '{model}' isn't downloaded. Run: ollama pull {model}", no_credits=True
            )
        if res.status_code != 200:
            raise ProviderError(
                f"Ollama error {res.status_code}: {res.text[:200]}", retryable=res.status_code >= 500
            )

        data = res.json()
        content = (data.get("message") or {}).get("content", "")
        try:
            result = json.loads(content)
        except ValueError:
            raise ProviderError("Ollama returned text that isn't valid JSON", retryable=True) from None
        log.info(
            "ollama call",
            extra={
                "model": model,
                "prompt_tokens": data.get("prompt_eval_count"),
                "output_tokens": data.get("eval_count"),
                "duration_ms": int((data.get("total_duration") or 0) / 1e6),
            },
        )
        return result  # type: ignore[no-any-return]
