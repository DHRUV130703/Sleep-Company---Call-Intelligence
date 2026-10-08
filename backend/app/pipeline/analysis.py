"""AI steps on a transcript: who is the agent (role mapping) and the full per-call analysis.

The AI's answer is validated (contracts.CallAnalysis) and then grounded:
- every quote is checked against the transcript; unverifiable quotes are flagged `verified: false`
- timestamps are taken from the transcript line the quote came from
- dates ("kal", "tomorrow") are resolved by code, relative to the call date
- intent bucket and quality % are computed by code from config
"""

import json
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from app.config import get_business, get_settings
from app.contracts import CallAnalysis, LabeledTranscript, RoleMap, json_schema_for
from app.errors import ErrorCode
from app.pipeline.errors import StageError
from app.pipeline.grounding import locate_quote, resolve_when, verify_quote
from app.prompts import render
from app.providers import get_llm
from app.providers.base import ProviderError

log = logging.getLogger("analysis")


def clock(t: float) -> str:
    t = max(0, int(t))
    return f"{t // 60:02d}:{t % 60:02d}"


def transcript_lines(segments: list[dict[str, Any]], use_roles: bool = True) -> str:
    out = []
    for n, s in enumerate(segments):
        who = (s.get("role") or "unknown").upper() if use_roles else s["speaker"]
        out.append(f"[{s.get('i', n)}][{clock(s['start'])}] {who}: {s['text']}")
    return "\n".join(out)


def provider_stage_error(exc: ProviderError) -> StageError:
    if exc.no_credits:
        return StageError(ErrorCode.PROVIDER_NO_CREDITS, detail=str(exc)[:160])
    if exc.retryable:
        return StageError(ErrorCode.PROVIDER_RATE_LIMIT, detail=str(exc)[:160], retryable=True)
    return StageError(ErrorCode.PROVIDER_ERROR, detail=str(exc)[:160])


# ---------------------------------------------------------------------------
# Who is speaking: agent or customer
# ---------------------------------------------------------------------------

SCRIPT_RULES = {
    "roman": "Write Hindi (and other Indian-language) words in Roman letters (Hinglish), e.g. 'Haan, kal aa sakta hoon'. Keep English words in English.",
    "devanagari": "Write Hindi words in Devanagari. Keep English words in Latin letters.",
    "english": "Translate everything into natural English.",
}


async def assign_speakers(segments: list[dict[str, Any]], script: str) -> list[dict[str, Any]]:
    """Return segments with role = "agent" | "customer" (and text cleaned up when Claude labels them).

    - Transcriber already said AGENT / CUSTOMER (Gemini) → use that.
    - Transcriber separated voices as S1/S2 or A/B (OpenAI, Gemini) → map_roles() picks which one is the agent.
    - Transcriber has no speakers at all (local Whisper, speaker "?") → label_speakers() asks Claude per line.
    """
    labels = {s["speaker"] for s in segments}
    if labels <= {"AGENT", "CUSTOMER", "OTHER"}:
        return [{**s, "role": "agent" if s["speaker"] == "AGENT" else "customer"} for s in segments]
    if labels == {"?"}:
        return await label_speakers(segments, script)
    roles = await map_roles(segments)
    return [{**s, "role": roles.get(s["speaker"], "customer")} for s in segments]


async def label_speakers(segments: list[dict[str, Any]], script: str) -> list[dict[str, Any]]:
    lines = "\n".join(f"[{n}][{clock(s['start'])}] {s['text']}" for n, s in enumerate(segments))
    prompt, _ = render(
        "label_speakers", script_rule=SCRIPT_RULES.get(script, SCRIPT_RULES["roman"]), lines=lines
    )
    try:
        data = await get_llm().json(
            prompt=prompt, schema=json_schema_for(LabeledTranscript), model=get_settings().analysis_model
        )
        labeled = {x.i: x for x in LabeledTranscript.model_validate(data).segments}
    except ProviderError as exc:
        raise provider_stage_error(exc) from exc
    except ValidationError as exc:
        log.warning("speaker labelling invalid; alternating speakers", extra={"reason": str(exc)[:200]})
        labeled = {}
    out = []
    for n, s in enumerate(segments):
        x = labeled.get(n)
        role = x.role if x else ("agent" if n % 2 == 0 else "customer")
        text = (x.text.strip() if x else "") or s["text"]
        out.append({**s, "speaker": role.upper(), "role": role, "text": text, "original_text": s["text"]})
    return out


async def map_roles(segments: list[dict[str, Any]]) -> dict[str, str]:
    """{speaker label → "agent" | "customer"}. Falls back to "first speaker is the agent"."""
    labels = list(dict.fromkeys(s["speaker"] for s in segments))
    if not labels:
        return {}
    first = labels[0]
    if len(labels) == 1:
        return {first: "agent"}
    agent = first
    try:
        prompt, _ = render(
            "role_map", lines=transcript_lines(segments[:30], use_roles=False), labels=", ".join(labels)
        )
        data = await get_llm().json(
            prompt=prompt, schema=json_schema_for(RoleMap), model=get_settings().lead_summary_model
        )
        guess = RoleMap.model_validate(data).agent_speaker.strip()
        if guess in labels:
            agent = guess
    except (ProviderError, ValidationError) as exc:
        log.warning("role mapping failed; first speaker = agent", extra={"reason": str(exc)[:200]})
    return {label: ("agent" if label == agent else "customer") for label in labels}


# ---------------------------------------------------------------------------
# Per-call analysis
# ---------------------------------------------------------------------------


async def analyse_transcript(
    segments: list[dict[str, Any]],
    *,
    agent_type: str,
    campaign: str,
    call_datetime: datetime | None,
    duration_s: float,
) -> tuple[dict[str, Any], str]:
    """Return (grounded analysis dict, prompt version)."""
    s = get_settings()
    b = get_business()
    tz = ZoneInfo(s.default_timezone)
    prompt, version = render(
        "analyze_call",
        agent_type="AI voice bot" if agent_type == "ai" else "Human sales agent",
        campaign=campaign or "(not given)",
        call_datetime=call_datetime.astimezone(tz).strftime("%a %d %b %Y, %H:%M")
        if call_datetime
        else "(unknown)",
        duration=clock(duration_s),
        scorecard="\n".join(f"- {d.key}: {d.label}. {d.guide}" for d in b.scorecard.dimensions),
        products="\n".join(
            f"- {p.name} ({p.category}): pitch when {p.pitch_when}" for p in b.catalog.products
        )
        or "(no catalog configured)",
        positive_signals="; ".join(b.intent.signals.positive),
        negative_signals="; ".join(b.intent.signals.negative),
        transcript=transcript_lines(segments),
    )
    schema = json_schema_for(CallAnalysis)
    llm = get_llm()

    analysis: CallAnalysis | None = None
    last_error = ""
    for attempt in range(2):  # one retry with the validation error explained
        ask = (
            prompt if attempt == 0 else f"{prompt}\n\nYour previous answer was invalid: {last_error}\nFix it."
        )
        try:
            data = await llm.json(prompt=ask, schema=schema, model=s.analysis_model)
        except ProviderError as exc:
            raise provider_stage_error(exc) from exc
        try:
            analysis = CallAnalysis.model_validate(data)
            break
        except ValidationError as exc:
            last_error = str(exc)[:1500]
    if analysis is None:
        raise StageError(ErrorCode.ANALYSIS_INVALID, detail=last_error[:200])

    return ground(analysis, segments, call_datetime, agent_type), version


def ground(
    analysis: CallAnalysis, segments: list[dict[str, Any]], call_dt: datetime | None, agent_type: str
) -> dict[str, Any]:
    s = get_settings()
    b = get_business()
    full_text = "\n".join(seg["text"] for seg in segments)
    out = analysis.model_dump()

    def check(item: dict[str, Any], quote_key: str, t_key: str = "t") -> None:
        quote = item.get(quote_key, "")
        item["verified"] = bool(quote) and verify_quote(quote, full_text)
        if item["verified"] and (seg := locate_quote(quote, segments)):
            item[t_key] = seg["start"]

    out["next_actions"] = [a for a in out["next_actions"] if a["title"].strip()]
    for o in out["objections"]:
        o["title"] = o["title"].strip() or o["type"].replace("_", " ").capitalize()
    known_types = set(b.intent.objection_types)
    for o in out["objections"]:
        if o["type"] not in known_types:
            o["type"] = "other"
        check(o, "customer_quote")
    for k in out["key_moments"]:
        check(k, "quote")
    for f in out["ai_failure_patterns"]:
        check(f, "quote")
    for p in out["pitch_opportunities"]:
        check(p, "evidence")
    for item in out["bant"].values():
        item["verified"] = bool(item["evidence"]) and verify_quote(item["evidence"], full_text)

    # Scorecard: keep known keys once each, in config order.
    by_key = {sc["key"]: sc for sc in out["scorecard"]}
    out["scorecard"] = []
    for d in b.scorecard.dimensions:
        if sc := by_key.get(d.key):
            check(sc, "evidence")
            out["scorecard"].append(sc)

    if agent_type != "ai":
        out["ai_failure_patterns"] = []

    # Dates resolved by code.
    out["outcome"]["next_step_due"] = _iso(
        resolve_when(out["outcome"]["next_step_when"], call_dt, s.default_timezone)
    )
    for a in out["next_actions"]:
        a["due"] = _iso(resolve_when(a["when"], call_dt, s.default_timezone))

    # Numbers computed by code.
    score = max(0, min(100, out["intent"]["score"]))
    bucket = b.intent.bucket_for(score)
    if out["outcome"]["disposition"] == "not_qualified":
        bucket = "not_qualified"
    out["intent"]["bucket"] = bucket
    scores = [sc["score"] for sc in out["scorecard"]]
    out["quality_pct"] = round((sum(scores) / len(scores) - 1) / 4 * 100, 1) if scores else None
    out["review_score"] = round(sum(scores) / len(scores), 2) if scores else None
    return out


def _iso(d: Any) -> str | None:
    return d.isoformat() if d else None


def compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
