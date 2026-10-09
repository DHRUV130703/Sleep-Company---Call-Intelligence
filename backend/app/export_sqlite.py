"""Export the report data from the database into a standalone SQLite file: `make export-sqlite`.

Writes exports/limezip-reports-<date>.db with plain, flat tables (one row per thing, no JSON) so it can
be opened with `sqlite3` or DB Browser for SQLite and queried directly:

    calls_report          one row per call: lead, outcome, scores, intent, summary
    call_scores           one row per call × scorecard dimension (score, reason, quote, better line)
    call_objections       every objection with how it was handled and a better response
    call_next_actions     the next steps written for each call
    transcript_lines      who said what, when
    leads                 one row per lead
    verdict               the latest AI vs Human verdict (all calls)
    verdict_points        its key points
    improvement_plan      ranked improvement parameters for the bot
    root_causes           repeated bot failures (+ root_cause_calls: every call where it happened)
    call_rca_issues       every issue in every bot call, on the call's timeline
    recommended_changes   AI-written changes to the bot

Reads the live database (DATABASE_URL); never changes it. Phone numbers follow MASK_PHONES.
"""

import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Any

from sqlmodel import Session, col, select

import app.models  # noqa: F401  (registers every table)
from app.config import PROJECT_ROOT
from app.db import get_engine
from app.models import Analysis, Call, Comparison, Lead, Transcript
from app.pipeline.compare import RESULT_VERSION
from app.pipeline.leads import display_phone

Rows = list[dict[str, Any]]


def _write(db: sqlite3.Connection, table: str, rows: Rows) -> None:
    if not rows:
        print(f"  {table}: 0 rows")
        return
    cols = list(rows[0])
    db.execute(f"CREATE TABLE {table} ({', '.join(cols)})")
    db.executemany(
        f"INSERT INTO {table} VALUES ({', '.join('?' for _ in cols)})",
        [[_cell(r.get(c)) for c in cols] for r in rows],
    )
    print(f"  {table}: {len(rows)} rows")


def _cell(v: Any) -> Any:
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    if isinstance(v, dict):
        return str(v)
    if v is not None and not isinstance(v, int | float | str):
        return str(v)  # enums, datetimes
    return v


def _call_tables(s: Session) -> dict[str, Rows]:
    calls = s.exec(select(Call).order_by(col(Call.id))).all()
    leads = {lead.id: lead for lead in s.exec(select(Lead))}
    analyses = {a.call_id: a for a in s.exec(select(Analysis).order_by(col(Analysis.id)))}
    out: dict[str, Rows] = {
        k: [] for k in ("calls_report", "call_scores", "call_objections", "call_next_actions")
    }
    for c in calls:
        a = analyses.get(c.id)  # type: ignore[arg-type]
        r = a.result if a else {}
        lead = leads.get(c.lead_id)
        base = {"call_id": c.id, "call": c.label, "agent_type": c.agent_type}
        out["calls_report"].append(
            {
                **base,
                "lead_id": c.lead_id,
                "lead_name": lead.name if lead else "",
                "phone": display_phone(lead.phone_e164) if lead else "",
                "agent_name": c.agent_name,
                "campaign": c.campaign,
                "call_datetime": c.call_datetime or c.created_at,
                "duration_s": c.duration_s,
                "status": c.status,
                "error": c.error_detail,
                "review_score": r.get("review_score"),
                "quality_pct": r.get("quality_pct"),
                "intent_score": (r.get("intent") or {}).get("score"),
                "intent_bucket": (r.get("intent") or {}).get("bucket"),
                "outcome": (r.get("outcome") or {}).get("disposition"),
                "next_step": (r.get("outcome") or {}).get("next_step"),
                "next_step_when": (r.get("outcome") or {}).get("next_step_when"),
                "mood_start": (r.get("mood") or {}).get("start"),
                "mood_end": (r.get("mood") or {}).get("end"),
                "language": r.get("language"),
                "summary": (r.get("summary") or {}).get("one_liner"),
                "summary_points": (r.get("summary") or {}).get("bullets"),
                "customer_name": (r.get("customer") or {}).get("name"),
                "city": (r.get("customer") or {}).get("city"),
                "products_discussed": (r.get("customer") or {}).get("products_discussed"),
                "pain_points": (r.get("customer") or {}).get("pain_points"),
                "budget": (r.get("customer") or {}).get("budget"),
                "unanswered_questions": r.get("unanswered_questions"),
                "bot_failures": [f["pattern"] for f in r.get("ai_failure_patterns", [])],
                "reviewed_with": a.prompt_version if a else None,
            }
        )
        out["call_scores"] += [
            {**base, "dimension": sc["key"], "score": sc["score"], "reason": sc.get("reason"),
             "quote": sc.get("evidence"), "at_second": sc.get("t"), "better": sc.get("better", "")}
            for sc in r.get("scorecard", [])
        ]  # fmt: skip
        out["call_objections"] += [
            {**base, "type": o["type"], "title": o.get("title"), "customer_quote": o.get("customer_quote"),
             "at_second": o.get("t"), "handled_well": o.get("handled_well"), "handling": o.get("handling"),
             "better_response": o.get("better_response")}
            for o in r.get("objections", [])
        ]  # fmt: skip
        out["call_next_actions"] += [
            {**base, "lead_id": c.lead_id, "title": n.get("title"), "say": n.get("say"), "why": n.get("why"),
             "due_when": n.get("when"), "due": n.get("due")}
            for n in r.get("next_actions", [])
        ]  # fmt: skip
    out["leads"] = [
        {"lead_id": lead.id, "name": lead.name, "phone": display_phone(lead.phone_e164), "status": lead.status,
         "intent_score": lead.intent_score, "intent_bucket": lead.intent_bucket, "owner": lead.owner,
         "assignee": lead.assignee, "last_call_at": lead.last_call_at}
        for lead in leads.values()
    ]  # fmt: skip
    return out


def _transcripts(s: Session) -> Rows:
    rows: Rows = []
    for t in s.exec(select(Transcript).order_by(col(Transcript.call_id), col(Transcript.id))):
        rows += [
            {"call_id": t.call_id, "line": seg.get("i"), "start_s": seg.get("start"), "role": seg.get("role"),
             "text": seg.get("text")}
            for seg in t.segments
        ]  # fmt: skip
    return rows


def _report_tables(s: Session) -> dict[str, Rows]:
    """The latest AI vs Human report over all calls (as saved by the AI vs Human page)."""
    latest = None
    for cmp in s.exec(select(Comparison).order_by(col(Comparison.id).desc())):
        sc = cmp.result.get("scope") or {}
        if cmp.result.get("version") == RESULT_VERSION and not sc.get("batch_ids") and not sc.get("campaign"):
            latest = cmp.result
            break
    if latest is None:
        print("  (no AI vs Human report saved yet — open the AI vs Human page once, then export again)")
        return {}
    imp, syn = latest["improvement"], latest.get("synthesis") or {}
    v = imp["verdict"]
    return {
        "verdict": [
            {"generated_at": latest["generated_at"], "verdict": v["label"], "readiness_pct": v["readiness_pct"],
             "gap": v["gap"], "bot_avg_score": latest["scores"]["ai"]["avg_review"],
             "human_avg_score": latest["scores"]["human"]["avg_review"],
             "bot_next_step_pct": v["positive_outcome_pct"]["ai"], "human_next_step_pct": v["positive_outcome_pct"]["human"],
             "fix_first": v["top_levers"], "headline": syn.get("verdict_headline"),
             "assessment": syn.get("verdict_detail"), "ai_summary_error": latest.get("synthesis_error")}
        ],
        "verdict_points": [{"n": i + 1, "point": p} for i, p in enumerate(v["points"])],
        "improvement_plan": [
            {"rank": i + 1, "priority": p["priority"], "parameter": p["label"], "bot": p["ai"], "humans": p["human"],
             "gap": p["gap"], "weak_bot_calls": p["weak_calls"], "of_bot_calls": p["of"], "owner": p["area"],
             "how_to_fix": p["fix"]}
            for i, p in enumerate(imp["parameters"])
        ],
        "root_causes": [
            {"failure": c["label"], "bot_calls": c["count"], "of_bot_calls": c["of"], "share_pct": c["share"],
             "priority": c["priority"], "owner": c["area"], "fix": c["fix"]}
            for c in imp["root_causes"]
        ],
        "root_cause_calls": [
            {"failure": c["label"], "call_id": h["call_id"], "call": h["label"], "lead_id": h["lead_id"],
             "what_happened": h["description"], "quote": h["quote"], "at_second": h["t"], "better": h["better"]}
            for c in imp["root_causes"] for h in c["calls"]
        ],
        "call_rca_issues": [
            {"call_id": x["call_id"], "call": x["label"], "lead_id": x["lead_id"], "call_score": x["review_score"],
             "outcome": x["outcome"], "at_second": i["t"], "kind": i["kind"], "issue": i["title"],
             "what_happened": i["detail"], "quote": i["quote"], "better": i["better"]}
            for x in imp["call_rca"] for i in x["issues"]
        ],
        "recommended_changes": [
            {"priority": ch["priority"], "area": ch.get("area"), "change": ch["change"], "why": ch["rationale"],
             "new_bot_line": ch.get("bot_line"), "example_calls": [e["label"] for e in ch.get("examples", [])]}
            for ch in syn.get("recommended_changes", [])
        ],
    }  # fmt: skip


def main() -> None:
    out_dir = PROJECT_ROOT / "exports"
    out_dir.mkdir(exist_ok=True)
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else out_dir / f"limezip-reports-{date.today()}.db"
    path.unlink(missing_ok=True)
    print(f"Exporting report data to {path} …")
    with Session(get_engine()) as s:
        tables = {**_call_tables(s), "transcript_lines": _transcripts(s), **_report_tables(s)}
    db = sqlite3.connect(path)
    with db:
        for name, rows in tables.items():
            _write(db, name, rows)
    db.close()
    print(f"Done. Open it with:  sqlite3 {path}")


if __name__ == "__main__":
    main()
