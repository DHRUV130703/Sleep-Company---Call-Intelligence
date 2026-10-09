"""The written part of the AI vs Human report: one AI call over the computed numbers + short call digests.

The prompt is kept small on purpose (worst bot calls and best human calls first, a fixed character
budget) so it fits free-tier token limits. Every evidence quote the AI returns is checked against
that call's transcript and dropped if it isn't there; example call ids must be real bot calls.
"""

import json
from typing import Any

from sqlmodel import Session, col, select

from app.config import get_settings
from app.contracts import ComparisonSynthesis, json_schema_for
from app.models import Analysis, Call, Transcript
from app.pipeline.grounding import locate_quote, verify_quote
from app.prompts import render
from app.providers import get_llm

DIGEST_BUDGET = 5000  # characters of call digests in the prompt
QUOTES_PER_CALL = 2


def _digest(c: Call, side: str, r: dict[str, Any]) -> str:
    quotes = [
        q
        for q in (
            [f["quote"] for f in r.get("ai_failure_patterns", []) if f.get("verified")]
            + [o["customer_quote"] for o in r.get("objections", []) if o.get("verified")]
            + [k["quote"] for k in r.get("key_moments", []) if k.get("verified")]
        )
        if q
    ][:QUOTES_PER_CALL]
    issues = "; ".join(
        f"{f['pattern']}: {f.get('description', '')}" for f in r.get("ai_failure_patterns", [])
    )
    return (
        f"call_id={c.id} side={side} outcome={r['outcome']['disposition']} review={r.get('review_score')}\n"
        f"  summary: {r['summary']['one_liner']}\n"
        + (f"  bot issues: {issues}\n" if issues else "")
        + "".join(f'  call_id={c.id} quote: "{q[:160]}"\n' for q in quotes)
    )


def _digests(done: dict[str, list[Call]], analyses: dict[int, Analysis]) -> str:
    """Alternate worst bot call / best human call until the budget is used."""

    def score(c: Call) -> float:
        return analyses[c.id].result.get("review_score") or 0  # type: ignore[index]

    queues = {"ai": sorted(done["ai"], key=score), "human": sorted(done["human"], key=score, reverse=True)}
    out: list[str] = []
    used = 0
    for i in range(max(len(queues["ai"]), len(queues["human"]))):
        for side in ("ai", "human"):
            if i < len(queues[side]):
                c = queues[side][i]
                d = _digest(c, side, analyses[c.id].result)  # type: ignore[index, arg-type]
                if used + len(d) > DIGEST_BUDGET:
                    return "\n".join(out)
                out.append(d)
                used += len(d)
    return "\n".join(out)


def _aggregates(agg: dict[str, Any]) -> str:
    imp = agg["improvement"]
    data = {
        "calls_analysed": {s: agg["scores"][s]["n"] for s in ("ai", "human")},
        "avg_review_score_of_5": {s: agg["scores"][s]["avg_review"] for s in ("ai", "human")},
        "verdict": {k: imp["verdict"][k] for k in ("status", "gap", "readiness_pct", "positive_outcome_pct")},
        "improvement_parameters": [
            {k: p[k] for k in ("key", "label", "ai", "human", "gap", "weak_share", "priority")}
            for p in imp["parameters"]
        ],
        "bot_failure_patterns": [
            {"pattern": c["pattern"], "in_calls": c["count"], "of": c["of"]} for c in imp["root_causes"]
        ],
        "objections_missed_by_bot": [
            {"type": o["type"], "missed": len(o["missed"]), "total": o["total"]} for o in imp["objections"]
        ],
        "metrics": agg["metrics"],
        "outcomes_pct": agg["outcomes"],
    }
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


async def synthesise(
    session: Session, agg: dict[str, Any], done: dict[str, list[Call]], analyses: dict[int, Analysis]
) -> dict[str, Any]:
    prompt, _ = render(
        "compare",
        sample_note=f"\nNote: {agg['sample_warning']} Avoid strong claims." if agg["sample_warning"] else "",
        aggregates=_aggregates(agg),
        digests=_digests(done, analyses),
    )
    data = await get_llm().json(
        prompt=prompt, schema=json_schema_for(ComparisonSynthesis), model=get_settings().analysis_model
    )
    synth = ComparisonSynthesis.model_validate(data).model_dump()

    calls = {c.id: c for side in ("ai", "human") for c in done[side]}
    transcripts = {
        t.call_id: t.segments
        for t in session.exec(select(Transcript).where(col(Transcript.call_id).in_(list(calls))))
    }
    for d in synth["differences"]:
        kept = []
        for ev in d["evidence"]:
            segs = transcripts.get(ev["call_id"])
            if not segs or not verify_quote(ev["quote"], " ".join(s["text"] for s in segs)):
                continue
            seg = locate_quote(ev["quote"], segs)
            c = calls[ev["call_id"]]
            kept.append({**ev, "t": seg["start"] if seg else 0, "label": c.label, "agent_type": c.agent_type})
        d["evidence"] = kept
    for ch in synth["recommended_changes"]:
        ids = [i for i in dict.fromkeys(ch.pop("call_ids")) if i in calls and calls[i].agent_type == "ai"]
        ch["examples"] = [
            {"call_id": i, "label": calls[i].label, "lead_id": calls[i].lead_id} for i in ids[:3]
        ]
    return synth
