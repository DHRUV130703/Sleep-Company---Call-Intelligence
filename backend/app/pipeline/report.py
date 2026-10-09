"""The AI vs Human report as a plain outline, shared by every document format.

    build_outline(result)  →  Report(title, meta, sections=[Section(heading, blocks=[...])])

Word (report_docx.py) and the print/PDF page (report_html.py) both render this same outline, so the
two formats always contain the same content. To change what the report says, change it here.

The bot improvement sections (verdict, improvement plan, root causes, objections, call-by-call RCA)
live in report_improvement.py; block types live in report_blocks.py.
"""

import contextlib
from datetime import datetime
from typing import Any

from app.pipeline.compare import OUTCOME_LABELS
from app.pipeline.report_blocks import (
    SIDES,
    Block,
    Bullets,
    Para,
    Quote,
    Report,
    Section,
    Sub,
    Table,
    call_href,
    clock,
    hours_mins,
    humanize,
    num,
)
from app.pipeline.report_improvement import (
    call_rca_section,
    improvement_section,
    objections_section,
    root_causes_section,
    verdict_section,
)

__all__ = ["Bullets", "Para", "Quote", "Report", "Section", "Sub", "Table", "build_outline"]


def _scope_text(scope: dict[str, Any]) -> str:
    parts = []
    if scope.get("batch_ids"):
        parts.append("batches " + ", ".join(f"#{b}" for b in scope["batch_ids"]))
    if scope.get("campaign"):
        parts.append(f"campaign “{scope['campaign']}”")
    if scope.get("date_from") or scope.get("date_to"):
        parts.append(f"dates {(scope.get('date_from') or '…')[:10]} to {(scope.get('date_to') or '…')[:10]}")
    if scope.get("comparable_only"):
        parts.append("comparable calls only")
    return "Calls included: " + ("; ".join(parts) if parts else "all calls")


# ---------------------------------------------------------------------------
# Sections A–H (same order as the page)
# ---------------------------------------------------------------------------


def _records(r: dict[str, Any]) -> Section:
    rec = r["records"]
    rows = [
        ["Uploaded", *(str(rec[s]["uploaded"]) for s, _ in SIDES), str(rec["ai"]["uploaded"] + rec["human"]["uploaded"])],
        ["Analysed", *(str(rec[s]["analysed"]) for s, _ in SIDES), str(rec["ai"]["analysed"] + rec["human"]["analysed"])],
        ["Failed", *(str(rec[s]["failed"]) for s, _ in SIDES), str(rec["ai"]["failed"] + rec["human"]["failed"])],
        ["Not connected", *(str(rec[s]["not_connected"]) for s, _ in SIDES),
         str(rec["ai"]["not_connected"] + rec["human"]["not_connected"])],
        ["Audio", *(hours_mins(rec[s]["audio_seconds"]) for s, _ in SIDES),
         hours_mins(rec["ai"]["audio_seconds"] + rec["human"]["audio_seconds"])],
    ]  # fmt: skip
    blocks: list[Block] = [
        Para("How many calls are behind every number in this report.", muted=True),
        Table(["", "AI voice bot", "Human agents", "Total"], rows),
    ]
    if r.get("sample_warning"):
        blocks.append(Para(f"Small sample. {r['sample_warning']}"))
    return Section("Records", blocks)


def _differences(r: dict[str, Any]) -> Section | None:
    diffs = (r.get("synthesis") or {}).get("differences") or []
    if not diffs:
        return None
    blocks: list[Block] = [
        Para("Written by the AI from the calls. Every quote was checked against the transcript.", muted=True)
    ]
    for d in diffs:
        blocks += [
            Sub(d["theme"]),
            Table(["AI voice bot", "Human agents"], [[d["ai"], d["human"]]]),
            Para(f"Why it matters: {d['why']}"),
        ]
        for ev in d.get("evidence", []):
            side = "AI voice bot" if ev.get("agent_type") == "ai" else "Human agents"
            blocks.append(
                Quote(
                    ev["quote"],
                    f"{side} · {ev.get('label', '')} · {clock(ev.get('t'))}",
                    call_href(ev["call_id"], ev.get("t")),
                )
            )
    return Section("Where they differ", blocks)


def _scores(r: dict[str, Any]) -> Section:
    rows = []
    for d in r["dimensions"]:
        diff = (d["human"] - d["ai"]) if d["ai"] is not None and d["human"] is not None else None
        rows.append(
            [
                d["label"],
                num(d["ai"]),
                num(d["human"]),
                "—"
                if diff is None
                else (f"Human +{diff:.1f}" if diff > 0 else f"AI +{-diff:.1f}" if diff < 0 else "Equal"),
            ]
        )
    return Section("Review scores (1 = poor … 5 = excellent)",
                   [Para("Average of the per-call reviews.", muted=True),
                    Table(["Dimension", "AI voice bot", "Human agents", "Higher"], rows)])  # fmt: skip


def _measured(r: dict[str, Any]) -> Section:
    rows = []
    for m in r["metrics"]:
        fmt = clock if m["key"] == "duration_s" else num
        rows.append([m["label"].replace(" (s)", ""), fmt(m["ai"]), fmt(m["human"])])
    return Section("Measured from the transcripts",
                   [Para("Counted directly from who said what, not judged by the AI. Averages per call.", muted=True),
                    Table(["Measure", "AI voice bot", "Human agents"], rows)])  # fmt: skip


def _outcomes(r: dict[str, Any]) -> Section:
    rows = [
        [OUTCOME_LABELS.get(o["key"], o["label"]), num(o["ai"], "%"), num(o["human"], "%")]
        for o in r["outcomes"]
    ]
    sig = r["signals"]

    def mood(side: str) -> str:
        m = sig[side]["mood_end"]
        return (
            f"{m.get('positive', 0)} positive, {m.get('neutral', 0)} neutral, {m.get('negative', 0)} negative"
        )

    signal_rows = [
        ["Customer mood at the end", mood("ai"), mood("human")],
        ["Mood improved / worsened", *(f"{sig[s]['mood_improved']} / {sig[s]['mood_worsened']}" for s, _ in SIDES)],
        ["Objections handled well", *(f"{sig[s]['objections_handled_well']} of {sig[s]['objections_total']}" for s, _ in SIDES)],
        ["Friction points per call", *(num(sig[s]["friction_per_call"]) for s, _ in SIDES)],
        ["Questions left unanswered per call", *(num(sig[s]["unanswered_per_call"]) for s, _ in SIDES)],
        ["Calls escalated", *(num(sig[s]["escalated_pct"], "%") for s, _ in SIDES)],
        ["Average intent score", *(num(sig[s]["avg_intent"]) for s, _ in SIDES)],
    ]  # fmt: skip
    return Section("Outcomes and customer mood", [
        Para("Share of reviewed calls per outcome.", muted=True),
        Table(["Outcome", "AI voice bot", "Human agents"], rows or [["No outcomes yet", "—", "—"]]),
        Sub("Other signals"),
        Table(["Signal", "AI voice bot", "Human agents"], signal_rows),
    ])  # fmt: skip


def _fix(r: dict[str, Any]) -> Section:
    """The AI-written recommendations: strengths per side, outcomes, and concrete changes to the bot."""
    syn = r.get("synthesis") or {}
    blocks: list[Block] = []
    changes = sorted(
        syn.get("recommended_changes") or [], key=lambda c: ["high", "medium", "low"].index(c["priority"])
    )
    if changes:
        rows = []
        for c in changes:
            examples = ", ".join(e["label"] for e in c.get("examples", []))
            rows.append(
                [c["priority"].title(), c.get("area") or "—", c["change"], c["rationale"],
                 f"“{c['bot_line']}”" if c.get("bot_line") else "—", examples or "—"]
            )  # fmt: skip
        blocks.append(Table(["Priority", "Area", "Change", "Why", "New bot line", "Example calls"], rows))
    if syn.get("ai_better"):
        blocks += [Sub("Where the AI does better"), Bullets(syn["ai_better"])]
    if syn.get("human_better"):
        blocks += [Sub("Where humans do better"), Bullets(syn["human_better"])]
    if syn.get("outcomes_paragraph"):
        blocks += [Sub("Outcomes"), Para(syn["outcomes_paragraph"])]
    if not blocks:
        blocks.append(Para(r.get("synthesis_error") or "No recommendations yet.", muted=True))
    return Section("Recommended changes to the bot", blocks)


def _every_call(r: dict[str, Any]) -> Section:
    blocks: list[Block] = []
    for side, label in SIDES:
        calls = r["calls"][side]
        blocks.append(Sub(f"{label} ({len(calls)} calls)"))
        rows = [[c["label"], clock(c["duration_s"]), (c["language"] or "—").title(),
                 OUTCOME_LABELS.get(c["outcome"] or "", humanize(c["status"])),
                 num(c["quality_pct"], "%") if c["quality_pct"] is not None else "—",
                 c["one_liner"] or ""] for c in calls]  # fmt: skip
        blocks.append(
            Table(
                ["Call", "Length", "Language", "Outcome", "Quality", "Summary"],
                rows or [["No calls", "", "", "", "", ""]],
            )
        )
    return Section("Every call", blocks)


def build_outline(result: dict[str, Any]) -> Report:
    built = result.get("generated_at") or ""
    with contextlib.suppress(ValueError):  # keep the raw text if it isn't a date
        built = datetime.fromisoformat(built).strftime("%d %b %Y, %H:%M UTC")
    sections = [
        _records(result),
        verdict_section(result),
        improvement_section(result),
        root_causes_section(result),
        objections_section(result),
        _fix(result),
        call_rca_section(result),
        _differences(result),
        _scores(result),
        _measured(result),
        _outcomes(result),
        _every_call(result),
    ]
    return Report(
        title="AI voice bot vs human agents",
        meta=[f"Report built {built}", _scope_text(result.get("scope") or {})],
        sections=[s for s in sections if s is not None],
    )
