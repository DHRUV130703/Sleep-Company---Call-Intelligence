"""Bot improvement sections of the shareable report (built from result["improvement"], see bot_improvement.py).

verdict_section      status, readiness, key points, AI headline, the two average scores
improvement_section  ranked parameters + the weakest bot moments next to the best human moments
root_causes_section  repeated failure patterns with owner area, fix and every affected call
objections_section   objections the bot missed, with the better response
call_rca_section     every bot call, worst first, with its issues on a timeline
"""

from typing import Any

from app.pipeline.compare import OUTCOME_LABELS
from app.pipeline.report_blocks import (
    SIDES,
    Block,
    Bullets,
    Para,
    Quote,
    Section,
    Sub,
    Table,
    call_href,
    clock,
    humanize,
    num,
)

PRIORITY_TEXT = {"high": "Fix first", "medium": "Fix next", "low": "Minor", "none": "OK"}


def _improvement(r: dict[str, Any]) -> dict[str, Any]:
    return r.get("improvement") or {}


def _bot_quote(ex: dict[str, Any], extra: str = "") -> Quote:
    src = f"AI voice bot · {ex['label']} · {clock(ex.get('t'))}" + (f" · {extra}" if extra else "")
    return Quote(ex["quote"], src, call_href(ex["call_id"], ex.get("t")))


def _human_quote(ex: dict[str, Any], extra: str = "") -> Quote:
    src = f"Human agents · {ex['label']} · {clock(ex.get('t'))}" + (f" · {extra}" if extra else "")
    return Quote(ex["quote"], src, call_href(ex["call_id"], ex.get("t")))


def verdict_section(r: dict[str, Any]) -> Section:
    v = _improvement(r).get("verdict") or {}
    syn = r.get("synthesis") or {}
    blocks: list[Block] = []
    if v.get("label"):
        ready = f" — {v['readiness_pct']}% of human quality" if v.get("readiness_pct") is not None else ""
        blocks.append(Sub(v["label"] + ready))
    if syn.get("verdict_headline"):
        blocks.append(Para(syn["verdict_headline"]))
    if syn.get("verdict_detail"):
        blocks.append(Para(syn["verdict_detail"]))
    elif r.get("synthesis_error"):
        blocks.append(Para(r["synthesis_error"], muted=True))
    if v.get("points"):
        blocks.append(Bullets(v["points"]))
    if v.get("top_levers"):
        blocks.append(Para("Fix first: " + ", ".join(v["top_levers"]) + "."))
    rows = []
    for side, label in SIDES:
        sc = r["scores"][side]
        avg = f"{num(sc['avg_review'])} / 5" if sc["avg_review"] is not None else "—"
        pos = (v.get("positive_outcome_pct") or {}).get(side)
        rows.append([label, avg, num(pos, "%") if pos is not None else "—", f"{sc['n']} of {sc['of']} calls"])
    blocks.append(Table(["", "Average review score", "Concrete next step", "Reviewed"], rows))
    return Section("Verdict", blocks)


def improvement_section(r: dict[str, Any]) -> Section | None:
    params = _improvement(r).get("parameters") or []
    if not params:
        return None
    rows = [
        [PRIORITY_TEXT[p["priority"]], p["label"], num(p["ai"]), num(p["human"]),
         f"−{p['gap']:.1f}" if p["gap"] and p["gap"] > 0 else f"+{-p['gap']:.1f}" if p["gap"] else "0",
         f"{p['weak_calls']} of {p['of']}", p["area"] or "—", p["fix"] or "—"]
        for p in params
    ]  # fmt: skip
    blocks: list[Block] = [
        Para(
            "Every review dimension, most important first. Gap = bot score minus the human benchmark. "
            "Weak = bot calls scoring 1–2. Numbers are computed from the per-call reviews.",
            muted=True,
        ),
        Table(
            ["Priority", "Parameter", "Bot", "Humans", "Gap", "Weak bot calls", "Owner", "How to fix"], rows
        ),
    ]
    for p in params:
        if p["priority"] not in ("high", "medium") or not (p["bot_examples"] or p["human_examples"]):
            continue
        blocks.append(Sub(f"{p['label']} — {PRIORITY_TEXT[p['priority']].lower()}"))
        for ex in p["bot_examples"]:
            note = f"scored {ex['score']}/5 — {ex['reason']}" if ex["reason"] else f"scored {ex['score']}/5"
            if ex["quote"]:
                blocks.append(_bot_quote(ex, note))
            else:
                blocks.append(Para(f"{ex['label']}: {note}"))
            if ex.get("better"):
                blocks.append(Para(f"Better: {ex['better']}"))
        for ex in p["human_examples"]:
            blocks.append(_human_quote(ex, f"what good looks like, scored {ex['score']}/5"))
    return Section("Improvement plan for the bot", blocks)


def root_causes_section(r: dict[str, Any]) -> Section | None:
    causes = _improvement(r).get("root_causes")
    if causes is None:
        return None
    if not causes:
        return Section(
            "Root causes — repeated bot failures", [Para("No failure patterns in the bot calls.", muted=True)]
        )
    blocks: list[Block] = [
        Table(
            ["Failure", "Bot calls", "Owner", "Fix"],
            [[c["label"], f"{c['count']} of {c['of']} ({c['share']}%)", c["area"] or "—", c["fix"] or "—"]
             for c in causes],
        )
    ]  # fmt: skip
    for c in causes:
        blocks.append(Sub(f"{c['label']} — {c['count']} of {c['of']} bot calls"))
        for hit in c["calls"]:
            if hit["quote"]:
                blocks.append(_bot_quote(hit, hit["description"]))
            else:
                blocks.append(Para(f"{hit['label']}: {hit['description']}"))
            if hit.get("better"):
                blocks.append(Para(f"Better: {hit['better']}"))
    return Section("Root causes — repeated bot failures", blocks)


def objections_section(r: dict[str, Any]) -> Section | None:
    rows = _improvement(r).get("objections")
    if not rows:
        return None
    blocks: list[Block] = []
    for o in rows:
        blocks.append(Sub(f"{o['label']} — {len(o['missed'])} of {o['total']} not handled by the bot"))
        for m in o["missed"]:
            if m["quote"]:
                blocks.append(_bot_quote(m, f"customer objection · bot: {m['handling'] or '—'}"))
            else:
                blocks.append(Para(f"{m['label']}: {m['title']} · bot: {m['handling'] or '—'}"))
            if m.get("better"):
                blocks.append(Para(f"Better: {m['better']}"))
        if ex := o.get("human_example"):
            blocks.append(_human_quote(ex, f"handled well: {ex['handling']}"))
    return Section("Objections the bot missed", blocks)


def call_rca_section(r: dict[str, Any]) -> Section | None:
    calls = _improvement(r).get("call_rca")
    if not calls:
        return None
    blocks: list[Block] = [
        Para("Every bot call, worst first. Times link to the moment in the call.", muted=True),
        Table(
            ["Call", "Score", "Outcome", "Issues", "Main issue"],
            [[c["label"], f"{num(c['review_score'])} / 5" if c["review_score"] is not None else "—",
              OUTCOME_LABELS.get(c["outcome"] or "", humanize(c["outcome"] or "—")), str(c["issue_count"]),
              c["main_issue"] or "—"] for c in calls],
        ),
    ]  # fmt: skip
    for c in calls:
        if not c["issues"]:
            continue
        blocks.append(Sub(f"{c['label']} — {num(c['review_score'])} / 5"))
        if c["one_liner"]:
            blocks.append(Para(c["one_liner"], muted=True))
        blocks.append(
            Table(
                ["Time", "Issue", "What happened", "Said", "Better"],
                [[clock(i["t"]) if i["t"] >= 0 else "—", i["title"], i["detail"] or "—",
                  f"“{i['quote']}”" if i["quote"] else "—", i["better"] or "—"] for i in c["issues"]],
            )
        )  # fmt: skip
    return Section("Call-by-call RCA (bot calls)", blocks)
