"""Groq (cloud LLM) — call analysis, speaker roles, lead summaries and the AI vs Human write-up.

Uses Groq's OpenAI-compatible REST API directly (the `groq` Python SDK wraps this same endpoint):
    POST https://api.groq.com/openai/v1/chat/completions   header: Authorization: Bearer <GROQ_API_KEY>
with
    response_format = {"type": "json_schema", "json_schema": {"name", "schema", "strict": true}}
        → Groq guarantees the answer matches our schema (qwen/qwen3.8-27b, openai/gpt-oss-* support strict mode)
    reasoning_effort = none | low | medium | high   (how much the model "thinks" before answering)
    reasoning_format = "hidden"                     (keep the thinking out of the JSON answer)
"""

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.providers.base import ProviderError, RateLimiter, with_retries

log = logging.getLogger("providers")

URL = "https://api.groq.com/openai/v1/chat/completions"
SYSTEM_PROMPT = (
    "You are a precise, fair analyst of sales phone calls for The Sleep Company (India). "
    "Answer only with JSON matching the schema, and follow the user's rules exactly."
)


def strict_schema(node: Any) -> Any:
    """Groq strict mode needs `additionalProperties: false` on every object (all fields are already required)."""
    if isinstance(node, dict):
        out = {k: strict_schema(v) for k, v in node.items() if k not in ("minimum", "maximum")}
        if out.get("type") == "object":
            out["additionalProperties"] = False
        return out
    if isinstance(node, list):
        return [strict_schema(v) for v in node]
    return node


class GroqClient:
    name = "groq"

    def __init__(
        self,
        api_key: str,
        rpm: int,
        reasoning_effort: str = "low",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key
        self.reasoning_effort = reasoning_effort
        self.limiter = RateLimiter(rpm)
        self.transport = transport  # tests pass a fake server here

    async def json(
        self, *, prompt: str, schema: dict[str, Any], model: str, audio: Path | None = None
    ) -> dict[str, Any]:
        if audio is not None:
            raise ProviderError("Groq analysis models don't take audio; transcription is done separately")
        body = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "result", "schema": strict_schema(schema), "strict": True},
            },
            "reasoning_effort": self.reasoning_effort,
            "reasoning_format": "hidden",
            "temperature": 0.2,
            "max_completion_tokens": 8192,
        }
        return await with_retries(lambda: self._post(body, model), what=f"groq:{model}")

    async def _post(self, body: dict[str, Any], model: str) -> dict[str, Any]:
        await self.limiter.wait()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(180, connect=15), transport=self.transport
            ) as client:
                res = await client.post(URL, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
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
                "Groq returned an answer that isn't the expected JSON", retryable=True
            ) from exc
        usage = data.get("usage") or {}
        log.info(
            "groq call",
            extra={
                "model": model,
                "prompt_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
                "duration_ms": int(1000 * float(usage.get("total_time") or 0)),
            },
        )
        return result  # type: ignore[no-any-return]


def _raise_for(res: httpx.Response) -> None:
    try:
        err = res.json().get("error") or {}
    except ValueError:
        err = {}
    msg = str(err.get("message") or res.text[:200])
    if res.status_code in (401, 403):
        raise ProviderError(f"Groq rejected the API key: {msg}", no_credits=True)
    if res.status_code in (413, 429):  # Groq uses both for "request too large for your plan"
        if (
            "request too large" in msg.lower()
        ):  # a single call is over the plan's per-minute cap: waiting won't help
            raise ProviderError(
                "This call is too large for your Groq plan's per-minute limit with this model. Use a model with "
                "higher limits (ANALYSIS_MODEL in .env) or upgrade your Groq plan, then click Retry.",
                no_credits=True,
            )
        if "per day" in msg.lower() or "(tpd)" in msg.lower() or "(rpd)" in msg.lower():
            raise ProviderError(f"Groq daily limit reached: {msg}", no_credits=True)
        wait = res.headers.get("retry-after")
        raise ProviderError(
            f"Groq rate limit: {msg}", retryable=True, retry_after=float(wait) if wait else 10
        )
    if res.status_code >= 500:
        raise ProviderError(f"Groq busy ({res.status_code}): {msg}", retryable=True)
    if res.status_code == 400 and "json" in msg.lower():  # the model's JSON didn't validate — try again
        raise ProviderError(f"Groq JSON check failed: {msg}", retryable=True)
    raise ProviderError(f"Groq error {res.status_code}: {msg}")
