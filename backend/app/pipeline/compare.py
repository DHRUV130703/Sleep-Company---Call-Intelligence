"""AI voice bot vs human agents (PRD §6.6, §7.5).

1. Aggregate in code: scores, metrics, outcomes, mood, objections, record counts.
2. Build the bot improvement plan in code (bot_improvement.py): verdict, ranked parameters, root causes,
   missed objections and call-by-call RCA — each example linked to its call and lead.
3. One AI call writes the narrative (verdict, differences, recommendations) — see compare_synthesis.py.
4. Every evidence quote is verified against that call's transcript; unverifiable evidence is dropped.
5. The result is cached per (scope, data version) so the page loads instantly until new calls arrive.
"""

import hashlib
import json
import logging
from collections import Counter
from datetime import UTC, datetime
from statistics import mean
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.config import get_business
from app.db import utcnow
from app.models import Analysis, Call, CallMetrics, CallStatus, Comparison
from app.pipeline.bot_improvement import build_improvement
from app.pipeline.compare_synthesis import synthesise
from app.pipeline.leads import NOT_CONNECTED_CODES
from app.pipeline.metrics import METRIC_LABELS
from app.prompts import current_version
from app.providers.base import ProviderError

log = logging.getLogger("compare")

SIDES = ("ai", "human")
MIN_RELIABLE = 10
RESULT_VERSION = 3  # bump when the result's shape changes, so cached results are rebuilt
OUTCOME_LABELS = {
    "converted": "Converted",
    "store_visit": "Store visit agreed",
    "callback_scheduled": "Callback scheduled",
    "agreed_next_step": "Agreed next step",
    "follow_up_pending": "Follow-up pending",
    "not_interested": "Not interested",
    "not_qualified": "Not qualified",
    "no_outcome": "No outcome",
}


def scope_filters(scope: dict[str, Any]) -> list[Any]:
    f: list[Any] = []
    if scope.get("batch_ids"):
        f.append(col(Call.batch_id).in_(scope["batch_ids"]))
    if scope.get("campaign"):
        f.append(Call.campaign == scope["campaign"])
    when = func.coalesce(Call.call_datetime, Call.created_at)
    if scope.get("date_from"):
        f.append(when >= _as_utc(scope["date_from"]))
    if scope.get("date_to"):
        f.append(when <= _as_utc(scope["date_to"]))
    return f


def _as_utc(iso: str) -> datetime:
    """Scope dates are stored as ISO text (so results can be cached as JSON)."""
    dt = datetime.fromisoformat(iso)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _scope_hash(scope: dict[str, Any]) -> str:
    return hashlib.sha1(json.dumps(scope, sort_keys=True, default=str).encode()).hexdigest()[:16]


def data_version(session: Session, scope: dict[str, Any]) -> str:
    """Changes whenever a call in scope changes (new call, new analysis, status change)."""
    row = session.exec(
        select(func.count(), func.max(Call.updated_at)).select_from(Call).where(*scope_filters(scope))
    ).one()
    last_analysis = session.exec(select(func.max(Analysis.id))).one()
    return f"{row[0]}:{row[1]}:{last_analysis}"


def cached_comparison(session: Session, scope: dict[str, Any]) -> dict[str, Any] | None:
    """The saved result for this scope, if no call in scope has changed since it was built."""
    cached = session.exec(
        select(Comparison)
        .where(
            Comparison.scope_hash == _scope_hash(scope),
            Comparison.data_version == data_version(session, scope),
        )
        .order_by(col(Comparison.id).desc())
    ).first()
    # Results built by an older version of this code lack newer sections: rebuild those.
    return cached.result if cached and cached.result.get("version") == RESULT_VERSION else None


async def build_comparison(session: Session, scope: dict[str, Any]) -> dict[str, Any]:
    b = get_business()
    calls = session.exec(select(Call).where(*scope_filters(scope)).order_by(col(Call.id))).all()
    ids = [c.id for c in calls]
    analyses = {a.call_id: a for a in session.exec(select(Analysis).where(col(Analysis.call_id).in_(ids)))}
    metrics = {
        m.call_id: m.data for m in session.exec(select(CallMetrics).where(col(CallMetrics.call_id).in_(ids)))
    }

    if scope.get("comparable_only"):
        calls = [c for c in calls if c.id in analyses and (c.duration_s or 0) >= 20]

    by_side: dict[str, list[Call]] = {s: [c for c in calls if c.agent_type == s] for s in SIDES}
    done: dict[str, list[Call]] = {s: [c for c in by_side[s] if c.id in analyses] for s in SIDES}

    # A. Records strip
    records = {}
    for side in SIDES:
        cs = by_side[side]
        records[side] = {
            "uploaded": len(cs),
            "analysed": len(done[side]),
            "failed": sum(1 for c in cs if c.status == CallStatus.failed),
            "not_connected": sum(
                1 for c in cs if c.status == CallStatus.skipped and c.error_code in NOT_CONNECTED_CODES
            ),
            "in_progress": sum(1 for c in cs if c.status in (CallStatus.queued, CallStatus.running)),
            "audio_seconds": round(sum(c.duration_s or 0 for c in cs), 1),
        }
    n_ai, n_h = len(done["ai"]), len(done["human"])
    sample_warning = None
    if min(n_ai, n_h) < MIN_RELIABLE:
        sample_warning = (
            f"Based on {n_ai} AI and {n_h} human calls. Add more calls (10+ per side) before "
            "changing the bot script."
        )

    def results(side: str) -> list[dict[str, Any]]:
        return [analyses[c.id].result for c in done[side]]  # type: ignore[index]

    # B. Average review score (1–5) per side
    def avg_review(side: str) -> float | None:
        vals = [r["review_score"] for r in results(side) if r.get("review_score") is not None]
        return round(mean(vals), 1) if vals else None

    # D. Dimension scores
    dimensions = []
    for d in b.scorecard.dimensions:
        row: dict[str, Any] = {"key": d.key, "label": d.label}
        for side in SIDES:
            vals = [sc["score"] for r in results(side) for sc in r.get("scorecard", []) if sc["key"] == d.key]
            row[side] = round(mean(vals), 1) if vals else None
            row[f"{side}_n"] = len(vals)
        dimensions.append(row)

    # E. Measured metrics (averages per call)
    metric_rows = []
    for k, label in METRIC_LABELS.items():
        row = {"key": k, "label": label}
        for side in SIDES:
            vals = [metrics[c.id][k] for c in done[side] if c.id in metrics and k in metrics[c.id]]
            row[side] = round(mean(vals), 1) if vals else None
        metric_rows.append(row)

    # F. Outcomes and other signals
    outcomes = []
    for k, label in OUTCOME_LABELS.items():
        row = {"key": k, "label": label}
        for side in SIDES:
            rs = results(side)
            row[side] = (
                round(100 * sum(1 for r in rs if r["outcome"]["disposition"] == k) / len(rs)) if rs else None
            )
        if any(row[side] for side in SIDES):
            outcomes.append(row)

    signals = {}
    for side in SIDES:
        rs = results(side)
        n = len(rs) or 1
        objs = [o for r in rs for o in r.get("objections", [])]
        signals[side] = {
            "mood_end": dict(Counter(r["mood"]["end"] for r in rs)),
            "mood_improved": sum(1 for r in rs if r["mood"]["trajectory"] == "improved"),
            "mood_worsened": sum(1 for r in rs if r["mood"]["trajectory"] == "worsened"),
            "objections_total": len(objs),
            "objections_handled_well": sum(1 for o in objs if o["handled_well"]),
            "friction_per_call": round(sum(len(r.get("friction_points", [])) for r in rs) / n, 1),
            "unanswered_per_call": round(sum(len(r.get("unanswered_questions", [])) for r in rs) / n, 1),
            "escalated_pct": round(100 * sum(1 for r in rs if r["outcome"]["escalated"]) / n),
            "avg_intent": round(mean(r["intent"]["score"] for r in rs)) if rs else None,
        }

    # H. Every call
    def call_row(c: Call) -> dict[str, Any]:
        a = analyses.get(c.id)  # type: ignore[arg-type]
        r = a.result if a else {}
        return {
            "id": c.id,
            "label": c.label,
            "duration_s": c.duration_s,
            "status": c.status,
            "error_code": c.error_code,
            "language": r.get("language"),
            "outcome": (r.get("outcome") or {}).get("disposition"),
            "quality_pct": a.quality_pct if a else None,
            "review_score": r.get("review_score"),
            "one_liner": (r.get("summary") or {}).get("one_liner"),
        }

    scores = {
        side: {"avg_review": avg_review(side), "n": len(done[side]), "of": len(by_side[side])}
        for side in SIDES
    }
    latest = current_version("analyze_call")
    outdated = [c for c in done["ai"] if analyses[c.id].prompt_version != latest]  # type: ignore[index]
    result: dict[str, Any] = {
        "version": RESULT_VERSION,
        # Bot calls reviewed with an older prompt lack newer fields (e.g. "better" lines): offer to update.
        "outdated_bot_reviews": len(outdated),
        "scope": scope,
        "generated_at": utcnow().isoformat(),
        "records": records,
        "sample_warning": sample_warning,
        "scores": scores,
        "improvement": build_improvement(done, analyses, scores),
        "dimensions": dimensions,
        "metrics": metric_rows,
        "outcomes": outcomes,
        "signals": signals,
        "calls": {side: [call_row(c) for c in by_side[side]] for side in SIDES},
        "synthesis": None,
        "synthesis_error": None,
    }

    if n_ai and n_h:
        try:
            result["synthesis"] = await synthesise(session, result, done, analyses)
        except (ProviderError, ValidationError) as exc:
            log.warning("comparison synthesis failed", extra={"reason": str(exc)[:200]})
            result["synthesis_error"] = (
                "The written summary couldn't be generated right now. The numbers below are complete."
            )
    else:
        result["synthesis_error"] = "Each side needs at least one analysed call for the written comparison."

    session.add(
        Comparison(scope_hash=_scope_hash(scope), data_version=data_version(session, scope), result=result)
    )
    session.commit()
    return result


def outdated_bot_calls(session: Session, scope: dict[str, Any]) -> list[Call]:
    """Analysed bot calls in scope whose review was made with an older analysis prompt."""
    latest = current_version("analyze_call")
    calls = session.exec(
        select(Call).where(*scope_filters(scope), Call.agent_type == "ai", Call.status == CallStatus.done)
    ).all()
    ids = [c.id for c in calls]
    versions = {
        a.call_id: a.prompt_version
        for a in session.exec(
            select(Analysis).where(col(Analysis.call_id).in_(ids)).order_by(col(Analysis.id))
        )
    }
    return [c for c in calls if c.id in versions and versions[c.id] != latest]


def export_rows(result: dict[str, Any], session: Session) -> list[dict[str, Any]]:
    """One row per call with every score and metric (CSV export)."""
    ids = [c["id"] for side in SIDES for c in result["calls"][side]]
    analyses = {
        a.call_id: a.result for a in session.exec(select(Analysis).where(col(Analysis.call_id).in_(ids)))
    }
    metrics = {
        m.call_id: m.data for m in session.exec(select(CallMetrics).where(col(CallMetrics.call_id).in_(ids)))
    }
    dims = get_business().scorecard.dimensions
    rows = []
    for side in SIDES:
        for c in result["calls"][side]:
            r = analyses.get(c["id"], {})
            m = metrics.get(c["id"], {})
            scores = {sc["key"]: sc["score"] for sc in r.get("scorecard", [])}
            row = {
                "call_id": c["id"],
                "label": c["label"],
                "agent_type": side,
                "status": c["status"],
                "duration_s": c["duration_s"],
                "outcome": c["outcome"],
                "quality_pct": c["quality_pct"],
                "review_score": c["review_score"],
                "intent_score": (r.get("intent") or {}).get("score"),
            }
            row.update({f"score_{d.key}": scores.get(d.key) for d in dims})
            row.update({f"metric_{k}": m.get(k) for k in METRIC_LABELS})
            rows.append(row)
    return rows


def parse_scope(
    batch_ids: str | None,
    campaign: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    comparable_only: bool,
) -> dict[str, Any]:
    ids = sorted({int(x) for x in (batch_ids or "").split(",") if x.strip().isdigit()})
    return {
        "batch_ids": ids,
        "campaign": campaign or "",
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "comparable_only": comparable_only,
    }
