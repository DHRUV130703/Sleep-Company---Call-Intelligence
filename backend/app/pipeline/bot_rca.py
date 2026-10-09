"""Root-cause analysis of the AI voice bot's calls — the drill-down half of the bot improvement plan.

    root_causes(ai_calls)  repeated failure patterns, each with every affected call, owner area and fix
    objections(done)       objection types the bot did not handle, with the better response + a human example
    call_rca(ai_calls)     every bot call with its issues on a timeline, worst call first

Every example carries {call_id, label, lead_id} so the page can link to the call (at the moment) and
the lead. Quotes are shown only when they passed grounding.verify_quote during analysis.
"""

from collections import defaultdict
from typing import Any

from app.config import BotPlaybook, get_business
from app.models import Call

# Per-call analysis results, keyed by call id.
Results = dict[int | None, dict[str, Any]]


def ref(c: Call) -> dict[str, Any]:
    """How every example points back to its call and lead (for links)."""
    return {"call_id": c.id, "label": c.label, "lead_id": c.lead_id}


def verified(item: dict[str, Any], key: str) -> str:
    return item.get(key, "") if item.get("verified") else ""


def humanize(key: str) -> str:
    s = key.replace("_", " ")
    return s[:1].upper() + s[1:]


def pattern_label(pattern: str, pb: BotPlaybook) -> str:
    entry = pb.failure_patterns.get(pattern)
    return entry.label if entry and entry.label else humanize(pattern)


def _issue(kind: str, title: str, detail: str, quote: str, t: float, better: str) -> dict[str, Any]:
    return {"kind": kind, "title": title, "detail": detail, "quote": quote, "t": t, "better": better}


def root_causes(ai_calls: list[Call], res: Results, pb: BotPlaybook) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in ai_calls:
        for fp in res[c.id].get("ai_failure_patterns", []):
            groups[fp["pattern"]].append(
                {**ref(c), "description": fp.get("description", ""), "quote": verified(fp, "quote"),
                 "t": fp.get("t", -1), "better": fp.get("better_line", "")}
            )  # fmt: skip
    out = []
    for pattern, hits in groups.items():
        entry = pb.failure_patterns.get(pattern)
        n_calls = len({h["call_id"] for h in hits})
        share = round(100 * n_calls / len(ai_calls)) if ai_calls else 0
        rule = pb.priority
        priority = (
            "high"
            if share >= rule.high.weak_share
            else "medium"
            if share >= rule.medium.weak_share
            else "low"
        )
        out.append(
            {
                "pattern": pattern,
                "label": pattern_label(pattern, pb),
                "area": entry.area if entry else "",
                "fix": entry.fix if entry else "",
                "count": n_calls,
                "of": len(ai_calls),
                "share": share,
                "priority": priority,
                "calls": hits,
            }
        )
    return sorted(out, key=lambda x: -x["count"])


def objections(done: dict[str, list[Call]], res: Results) -> list[dict[str, Any]]:
    by_type: dict[str, dict[str, Any]] = {}
    for c in done["ai"]:
        for o in res[c.id].get("objections", []):
            row = by_type.setdefault(
                o["type"],
                {"type": o["type"], "label": humanize(o["type"]), "total": 0, "handled_well": 0,
                 "missed": [], "human_example": None},
            )  # fmt: skip
            row["total"] += 1
            if o.get("handled_well"):
                row["handled_well"] += 1
                continue
            row["missed"].append(
                {**ref(c), "title": o.get("title", ""), "quote": verified(o, "customer_quote"),
                 "t": o.get("t", -1), "handling": o.get("handling", ""), "better": o.get("better_response", "")}
            )  # fmt: skip
    for c in done["human"]:  # "what good looks like": the first well-handled human example per type
        for o in res[c.id].get("objections", []):
            target = by_type.get(o["type"])
            if target and target["human_example"] is None and o.get("handled_well") and o.get("verified"):
                target["human_example"] = {**ref(c), "quote": o["customer_quote"], "t": o.get("t", -1),
                                           "handling": o.get("handling", "")}  # fmt: skip
    return sorted((r for r in by_type.values() if r["missed"]), key=lambda r: -len(r["missed"]))


def _issues(r: dict[str, Any], pb: BotPlaybook, dim_labels: dict[str, str]) -> list[dict[str, Any]]:
    issues = [
        _issue("failure", pattern_label(fp["pattern"], pb), fp.get("description", ""),
               verified(fp, "quote"), fp.get("t", -1), fp.get("better_line", ""))
        for fp in r.get("ai_failure_patterns", [])
    ]  # fmt: skip
    issues += [
        _issue("objection", f"Objection not handled: {o.get('title') or humanize(o['type'])}",
               o.get("handling", ""), verified(o, "customer_quote"), o.get("t", -1), o.get("better_response", ""))
        for o in r.get("objections", [])
        if not o.get("handled_well")
    ]  # fmt: skip
    issues += [
        _issue("weak_score", f"{dim_labels.get(sc['key'], sc['key'])}: {sc['score']}/5", sc.get("reason", ""),
               verified(sc, "evidence"), sc.get("t", -1), sc.get("better", ""))
        for sc in r.get("scorecard", [])
        if sc["score"] <= pb.weak_score
    ]  # fmt: skip
    issues += [
        _issue("unanswered", "Question left unanswered", q, "", -1, "")
        for q in r.get("unanswered_questions", [])
    ]
    return sorted(issues, key=lambda i: (i["t"] < 0, i["t"]))  # call timeline; untimed last


def call_rca(ai_calls: list[Call], res: Results, pb: BotPlaybook) -> list[dict[str, Any]]:
    dim_labels = {d.key: d.label for d in get_business().scorecard.dimensions}
    rows = []
    for c in ai_calls:
        r = res[c.id]
        issues = _issues(r, pb, dim_labels)
        failures = [i["title"] for i in issues if i["kind"] == "failure"]
        rows.append(
            {
                **ref(c),
                "duration_s": c.duration_s,
                "review_score": r.get("review_score"),
                "outcome": (r.get("outcome") or {}).get("disposition"),
                "mood_end": (r.get("mood") or {}).get("end"),
                "one_liner": (r.get("summary") or {}).get("one_liner", ""),
                "main_issue": failures[0] if failures else issues[0]["title"] if issues else "",
                "issue_count": len(issues),
                "issues": issues,
            }
        )

    def worst_first(x: dict[str, Any]) -> tuple[float, int]:
        return (x["review_score"] if x["review_score"] is not None else 99, -x["issue_count"])

    return sorted(rows, key=worst_first)
