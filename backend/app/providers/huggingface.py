"""Hugging Face Inference Providers (cloud LLM) — the backup for call analysis when Groq's free day runs out.

Hugging Face routes one OpenAI-compatible API to many hosts (DeepInfra, Together, Groq, …):
    POST https://router.huggingface.co/v1/chat/completions   header: Authorization: Bearer <HF_TOKEN>
HF_MODEL picks the model and the host, e.g. "openai/gpt-oss-120b:cheapest" = the same model we use on Groq,
on whichever host is cheapest, so the monthly free credit lasts longest. Requests are billed from the
account's credit (free accounts: about $0.10 a month); when it runs out, HF answers 402.

Token: huggingface.co/settings/tokens → fine-grained → "Make calls to Inference Providers".
"""

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.providers.base import ProviderError, RateLimiter, with_retries
from app.providers.groq import SYSTEM_PROMPT, strict_schema

log = logging.getLogger("providers")

URL = "https://router.huggingface.co/v1/chat/completions"


class HuggingFaceClient:
    name = "huggingface"

    def __init__(
        self,
        token: str,
        model: str,
        rpm: int = 30,
        reasoning_effort: str = "low",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.token = token
        self.model = model  # used for every request (it names the host too, e.g. ":cheapest")
        self.reasoning_effort = reasoning_effort
        self.limiter = RateLimiter(rpm)
        self.transport = transport  # tests pass a fake server here

    async def json(
        self, *, prompt: str, schema: dict[str, Any], model: str, audio: Path | None = None
    ) -> dict[str, Any]:
        """`model` (the main analyser's model name) is ignored: HF_MODEL decides what runs here."""
        if audio is not None:
            raise ProviderError(
                "Hugging Face analysis models don't take audio; transcription is done separately"
            )
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "result", "schema": strict_schema(schema), "strict": True},
            },
            "reasoning_effort": self.reasoning_effort,
            "temperature": 0.2,
            "max_tokens": 8192,
        }
        return await with_retries(lambda: self._post(body), what=f"huggingface:{self.model}")

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        await self.limiter.wait()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(180, connect=15), transport=self.transport
            ) as client:
                res = await client.post(URL, json=body, headers={"Authorization": f"Bearer {self.token}"})
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc}", retryable=True) from exc
        if res.status_code != 200:
            _raise_for(res)
        data = res.json()
        try:
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError(
                "Hugging Face returned an answer that isn't the expected JSON", retryable=True
            ) from exc
        usage = data.get("usage") or {}
        log.info(
            "huggingface call",
            extra={"model": self.model, "prompt_tokens": usage.get("prompt_tokens"),
                   "output_tokens": usage.get("completion_tokens")},
        )  # fmt: skip
        return result  # type: ignore[no-any-return]


def _raise_for(res: httpx.Response) -> None:
    try:
        body = res.json()
        err = body.get("error") if isinstance(body, dict) else None
        msg = str(err.get("message") if isinstance(err, dict) else err or res.text[:200])
    except ValueError:
        msg = res.text[:200]
    if res.status_code in (401, 403):
        raise ProviderError(f"Hugging Face rejected the token (HF_TOKEN): {msg}", no_credits=True)
    if res.status_code == 402:
        raise ProviderError(f"Hugging Face monthly credit used up: {msg}", no_credits=True)
    if res.status_code == 429 or res.status_code >= 500:
        wait = res.headers.get("retry-after")
        raise ProviderError(
            f"Hugging Face busy ({res.status_code}): {msg}",
            retryable=True,
            retry_after=float(wait) if wait else 10,
        )
    if res.status_code == 400 and "json" in msg.lower():  # the model's JSON didn't validate — try again
        raise ProviderError(f"Hugging Face JSON check failed: {msg}", retryable=True)
    raise ProviderError(f"Hugging Face error {res.status_code}: {msg}")
