"""Hugging Face as the backup analyser (fake servers; no network, no key needed)."""

import json

import httpx
import pytest

from app import config, providers
from app.providers import LLMWithFallback, huggingface
from app.providers.base import ProviderError
from app.providers.groq import GroqClient
from app.providers.huggingface import HuggingFaceClient

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


def hf_server(status: int = 200, seen: list | None = None):
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.host == "router.huggingface.co" and req.headers["authorization"] == "Bearer hf-test"
        body = json.loads(req.content)
        if seen is not None:
            seen.append(body)
        if status != 200:
            return httpx.Response(status, json={"error": "You have exceeded your monthly included credits"})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {}})

    return httpx.MockTransport(handler)


async def test_sends_our_json_schema_to_the_configured_model():
    seen: list = []
    hf = HuggingFaceClient(
        "hf-test", "openai/gpt-oss-120b:cheapest", rpm=1000, transport=hf_server(seen=seen)
    )
    assert await hf.json(prompt="p", schema=SCHEMA, model="groq-model-name-is-ignored") == {"ok": True}
    body = seen[0]
    assert body["model"] == "openai/gpt-oss-120b:cheapest"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"]["additionalProperties"] is False


async def test_used_up_credit_is_reported_as_no_credits():
    hf = HuggingFaceClient("hf-test", "m", rpm=1000, transport=hf_server(status=402))
    with pytest.raises(ProviderError) as e:
        await hf.json(prompt="p", schema=SCHEMA, model="m")
    assert e.value.no_credits and "monthly credit" in str(e.value)


async def test_switches_to_hugging_face_when_groq_daily_limit_is_reached(monkeypatch):
    def groq_out_of_tokens(req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Rate limit reached ... tokens per day (TPD)"}})

    calls = {"groq": 0, "hf": 0}

    def build(name: str):
        calls["hf" if name == "huggingface" else "groq"] += 1
        if name == "groq":
            return GroqClient("k", 1000, transport=httpx.MockTransport(groq_out_of_tokens))
        return HuggingFaceClient("hf-test", "openai/gpt-oss-120b:cheapest", rpm=1000, transport=hf_server())

    monkeypatch.setattr(providers, "_build_llm", build)
    llm = LLMWithFallback("groq", "huggingface")
    assert await llm.json(prompt="p", schema=SCHEMA, model="openai/gpt-oss-120b") == {"ok": True}
    assert await llm.json(prompt="p", schema=SCHEMA, model="openai/gpt-oss-120b") == {"ok": True}
    assert calls == {"groq": 1, "hf": 2}  # after Groq's "daily limit", it isn't asked again for a while


async def test_backup_needs_its_token(monkeypatch):
    monkeypatch.setenv("ANALYZER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("ANALYZER_FALLBACK", "huggingface")
    monkeypatch.setenv("HF_TOKEN", "")
    config.get_settings.cache_clear()
    providers.reset_providers()
    with pytest.raises(ProviderError, match="HF_TOKEN is empty"):
        await providers.get_llm().json(prompt="p", schema=SCHEMA, model="m")
    providers.reset_providers()


def test_hf_module_points_at_the_router():
    assert huggingface.URL == "https://router.huggingface.co/v1/chat/completions"
