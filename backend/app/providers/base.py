"""Shared provider pieces: interfaces, error types, rate limiting and retries.

Vendor HTTP APIs are only called inside app/providers/. Everything else uses:
    get_transcriber() → Transcriber      (audio → speaker-labelled segments)
    get_llm()         → LLM              (prompt [+ audio] → JSON that matches a schema)
"""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol

from app.contracts import RawTranscript

log = logging.getLogger("providers")


class ProviderError(Exception):
    """A provider call failed.

    retryable   → try again later (rate limit, overload, network)
    no_credits  → the account is out of credits/quota; switch to the fallback provider
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        no_credits: bool = False,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.no_credits = no_credits
        self.retry_after = retry_after


class Transcriber(Protocol):
    name: str
    model: str

    async def transcribe(self, audio: Path, *, script: str, context: str = "") -> RawTranscript: ...


class LLM(Protocol):
    name: str

    async def json(
        self, *, prompt: str, schema: dict[str, Any], model: str, audio: Path | None = None
    ) -> dict[str, Any]: ...


class RateLimiter:
    """Allows at most `rpm` calls per rolling minute (shared by every task in this process)."""

    def __init__(self, rpm: int):
        self.interval = 60.0 / max(rpm, 1)
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self.interval
        if delay > 0:
            await asyncio.sleep(delay)


async def with_retries[T](
    fn: Callable[[], Awaitable[T]], *, what: str, max_attempts: int = 4, base_delay: float = 2.0
) -> T:
    """Run `fn`, retrying retryable ProviderErrors with exponential backoff + jitter."""
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except ProviderError as exc:
            if not exc.retryable or attempt == max_attempts:
                raise
            delay = exc.retry_after or base_delay * 2 ** (attempt - 1)
            delay = min(delay, 60) + random.uniform(0, 1)
            log.warning(
                "retrying provider call",
                extra={"what": what, "attempt": attempt, "delay_s": delay, "reason": str(exc)[:200]},
            )
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")
