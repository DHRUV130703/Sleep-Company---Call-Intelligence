"""Claude via the local `claude` command-line tool (Claude Code) — uses YOUR logged-in Claude account,
so no API key is needed. One-time setup in a terminal:  claude   then type  /login

Each request runs:
    claude -p --output-format json --json-schema <schema> --model <model> --tools "" ...
with the prompt on stdin, and reads the validated JSON from the result's "structured_output".
Claude can't listen to audio, so `audio` is not supported here (transcription is done by Whisper).
"""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from app.providers.base import ProviderError, with_retries

log = logging.getLogger("providers")

SYSTEM_PROMPT = (
    "You are a precise analyst of sales phone calls for The Sleep Company (India). "
    "Answer only through the structured output, following the user's rules exactly."
)
TIMEOUT_S = 600


class ClaudeCLI:
    name = "claude"

    def __init__(self, cli_path: str, concurrency: int, work_dir: Path):
        self.cli = shutil.which(cli_path) or cli_path
        self.work_dir = work_dir  # an empty folder, so Claude doesn't pick up project files
        self._slots = asyncio.Semaphore(max(1, concurrency))

    async def json(
        self, *, prompt: str, schema: dict[str, Any], model: str, audio: Path | None = None
    ) -> dict[str, Any]:
        if audio is not None:
            raise ProviderError("Claude can't process audio; use Whisper for transcription")
        return await with_retries(
            lambda: self._run(prompt, schema, model), what=f"claude:{model}", max_attempts=3
        )

    async def _run(self, prompt: str, schema: dict[str, Any], model: str) -> dict[str, Any]:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        args = [
            self.cli, "-p",
            "--output-format", "json",
            "--json-schema", json.dumps(schema),
            "--model", model,
            "--tools", "",  # no file/shell tools: it only reads the prompt and answers
            "--system-prompt", SYSTEM_PROMPT,
            "--no-session-persistence",
            "--strict-mcp-config",
        ]  # fmt: skip
        async with self._slots:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    cwd=self.work_dir,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError as exc:
                raise ProviderError(
                    "The `claude` command isn't installed or isn't on PATH (set CLAUDE_CLI_PATH in .env).",
                    no_credits=True,
                ) from exc
            try:
                out, err = await asyncio.wait_for(proc.communicate(prompt.encode()), timeout=TIMEOUT_S)
            except TimeoutError:
                proc.kill()
                raise ProviderError("Claude took too long to answer", retryable=True) from None

        try:
            data = json.loads(out.decode() or "{}")
        except ValueError:
            raise ProviderError(
                f"Claude returned unreadable output: {err.decode()[:200]}", retryable=True
            ) from None

        if data.get("is_error") or data.get("subtype") != "success":
            msg = str(data.get("result") or err.decode() or "unknown error")[:300]
            low = msg.lower()
            if "not logged in" in low or "/login" in low or "invalid api key" in low:
                raise ProviderError(
                    "Claude isn't logged in. In a terminal run: claude auth login — then click Retry",
                    no_credits=True,
                )
            if "limit" in low or "overloaded" in low or "rate" in low or "529" in low:
                raise ProviderError(f"Claude usage limit or busy: {msg}", retryable=True, retry_after=60)
            raise ProviderError(f"Claude error: {msg}", retryable=True)

        result = data.get("structured_output")
        if result is None:  # older CLI versions put the JSON in "result" as text
            try:
                result = json.loads(data.get("result") or "")
            except ValueError:
                raise ProviderError("Claude didn't return the expected JSON", retryable=True) from None
        log.info(
            "claude call",
            extra={
                "model": model,
                "cost_usd": data.get("total_cost_usd"),
                "duration_ms": data.get("duration_ms"),
            },
        )
        return result  # type: ignore[no-any-return]
