"""Groq integration against a fake Groq server (no network, no key needed)."""

import json

import httpx
import pytest

from app.providers.base import ProviderError
from app.providers.groq import GroqClient, strict_schema

SCHEMA = {"type": "object", "properties": {"n": {"type": "integer", "minimum": 0},
          "item": {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}},
          "required": ["n", "item"]}  # fmt: skip


def test_strict_schema_closes_every_object():
    s = strict_schema(SCHEMA)
    assert s["additionalProperties"] is False and s["properties"]["item"]["additionalProperties"] is False
    assert "minimum" not in s["properties"]["n"]


def fake_groq(responses: list[httpx.Response]):
    sent: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"] == "Bearer test-key"
        sent.append(json.loads(req.content))
        return responses.pop(0)

    return httpx.MockTransport(handler), sent


def ok(content: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


async def test_returns_parsed_json_and_sends_strict_schema(monkeypatch):
    transport, sent = fake_groq([ok({"n": 3, "item": {"a": "x"}})])
    client = GroqClient("test-key", rpm=1000, reasoning_effort="low", transport=transport)
    assert await client.json(prompt="hi", schema=SCHEMA, model="qwen/qwen3.8-27b") == {
        "n": 3,
        "item": {"a": "x"},
    }
    body = sent[0]
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["reasoning_format"] == "hidden" and body["reasoning_effort"] == "low"


async def test_rate_limit_is_retried(monkeypatch):
    monkeypatch.setattr("app.providers.base.asyncio.sleep", _no_sleep)
    transport, sent = fake_groq([
        httpx.Response(429, headers={"retry-after": "1"}, json={"error": {"message": "Rate limit reached (TPM)"}}),
        ok({"n": 1, "item": {"a": "y"}}),
    ])  # fmt: skip
    client = GroqClient("test-key", rpm=1000, transport=transport)
    assert (await client.json(prompt="hi", schema=SCHEMA, model="m"))["n"] == 1
    assert len(sent) == 2


@pytest.mark.parametrize(("status", "message"), [
    (401, "Invalid API Key"),
    (429, "Rate limit reached on tokens per day (TPD)"),
])  # fmt: skip
async def test_bad_key_and_daily_limit_fail_clearly(status, message):
    transport, _ = fake_groq([httpx.Response(status, json={"error": {"message": message}})])
    with pytest.raises(ProviderError) as e:
        await GroqClient("test-key", rpm=1000, transport=transport).json(
            prompt="hi", schema=SCHEMA, model="m"
        )
    assert e.value.no_credits and not e.value.retryable


async def _no_sleep(_seconds: float) -> None:
    return None


@pytest.mark.parametrize("status", [413, 429])
async def test_request_too_large_for_plan_is_not_retried(status):
    transport, sent = fake_groq([httpx.Response(status, json={"error": {"message": (
        "Request too large for model `qwen/qwen3.8-27b` on output tokens per minute (OTPM): Limit 1000, Requested 3085")}})])  # fmt: skip
    with pytest.raises(ProviderError, match="too large for your Groq plan") as e:
        await GroqClient("test-key", rpm=1000, transport=transport).json(
            prompt="hi", schema=SCHEMA, model="m"
        )
    assert e.value.no_credits and len(sent) == 1  # no pointless retries
