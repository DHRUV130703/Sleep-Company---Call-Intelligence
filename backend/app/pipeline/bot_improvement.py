"""Bot improvement plan for the AI vs Human page: what to change in the AI voice bot, with proof.

Everything here is computed in code from the per-call reviews (no AI call), so it is always complete,
even when the written summary can't be generated:

    verdict      is the bot behind, on par or ahead of humans — and by how much
    parameters   every scorecard dimension, ranked by how much fixing it would help (gap × how often),
                 with the weakest bot moments and the best human moments as examples
    root_causes, objections, call_rca   the drill-down — see bot_rca.py

Ranking rules, owner areas and fixes come from config/bot_playbook.yaml.
"""

from statistics import mean
from typing import Any

from app.config import BotPlaybook, get_business
from app.models import Analysis, Call
from app.pipeline.bot_rca import Results, call_rca, objections, ref, root_causes, verified

SIDES = ("ai", "human")
POSITIVE_OUTCOMES = ("converted", "store_visit", "callback_scheduled", "agreed_next_step")
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2, "none": 3}
MAX_BOT_EXAMPLES = 4
MAX_HUMAN_EXAMPLES = 2


def priority_for(gap: float | None, weak_share: float, pb: BotPlaybook) -> str:
    """high / medium / low / none — from how far behind humans the bot is and how often it is weak."""
    if gap is None:
        return "none"
    if gap >= pb.priority.high.gap or weak_share >= pb.priority.high.weak_share:
        return "high"
    if gap >= pb.priority.medium.gap or weak_share >= pb.priority.medium.weak_share:
        return "medium"
    if gap > pb.on_par_margin or weak_share > 0:
        return "low"
    return "none"


def status_for(gap: float | None, pb: BotPlaybook) -> str:
    if gap is None:
        return "no_data"
    return "behind" if gap > pb.on_par_margin else "ahead" if gap < -pb.on_par_margin else "on_par"


def _parameters(done: dict[str, list[Call]], res: Results, pb: BotPlaybook) -> list[dict[str, Any]]:
    """One improvement parameter per scorecard dimension, most important first."""
    rows = []
    for d in get_business().scorecard.dimensions:
        items = {
            side: [(c, sc) for c in done[side] for sc in res[c.id].get("scorecard", []) if sc["key"] == d.key]
            for side in SIDES
        }
        ai = round(mean(sc["score"] for _, sc in items["ai"]), 1) if items["ai"] else None
        human = round(mean(sc["score"] for _, sc in items["human"]), 1) if items["human"] else None
        target = human if human is not None else pb.target_score
        gap = round(target - ai, 1) if ai is not None else None
        weak = sum(1 for _, sc in items["ai"] if sc["score"] <= pb.weak_score)
        weak_share = round(100 * weak / len(items["ai"])) if items["ai"] else 0

        worst_ai = sorted((x for x in items["ai"] if x[1]["score"] <= 3), key=lambda x: x[1]["score"])
        best_human = sorted(
            (x for x in items["human"] if x[1]["score"] >= 4 and x[1].get("verified")),
            key=lambda x: -x[1]["score"],
        )
        entry = pb.dimensions.get(d.key)
        rows.append(
            {
                "key": d.key,
                "label": d.label,
                "area": entry.area if entry else "",
                "fix": entry.fix if entry else "",
                "ai": ai,
                "human": human,
                "target": target,
                "gap": gap,
                "weak_calls": weak,
                "of": len(items["ai"]),
                "weak_share": weak_share,
                "priority": priority_for(gap, weak_share, pb),
                "status": status_for(gap, pb),
                "bot_examples": [
                    {**ref(c), "score": sc["score"], "reason": sc.get("reason", ""),
                     "quote": verified(sc, "evidence"), "t": sc.get("t", -1), "better": sc.get("better", "")}
                    for c, sc in worst_ai[:MAX_BOT_EXAMPLES]
                ],
                "human_examples": [
                    {**ref(c), "score": sc["score"], "reason": sc.get("reason", ""),
                     "quote": sc["evidence"], "t": sc.get("t", -1)}
                    for c, sc in best_human[:MAX_HUMAN_EXAMPLES]
                ],
            }
        )  # fmt: skip
    return sorted(rows, key=lambda r: (PRIORITY_RANK[r["priority"]], -(r["gap"] or 0), -r["weak_share"]))


def _positive_pct(calls: list[Call], res: Results) -> int | None:
    if not calls:
        return None
    hits = sum(1 for c in calls if res[c.id]["outcome"]["disposition"] in POSITIVE_OUTCOMES)
    return round(100 * hits / len(calls))


VERDICT_LABELS = {
    "behind": "The bot is behind human agents",
    "on_par": "The bot is on par with human agents",
    "ahead": "The bot is ahead of human agents",
    "no_benchmark": "No human calls to benchmark against",
    "no_data": "No analysed bot calls yet",
}


def _verdict(
    scores: dict[str, Any],
    params: list[dict],
    causes: list[dict],
    positive: dict[str, int | None],
    pb: BotPlaybook,
) -> dict[str, Any]:
    ai, human = scores["ai"]["avg_review"], scores["human"]["avg_review"]
    gap = round(human - ai, 1) if ai is not None and human is not None else None
    status = "no_data" if ai is None else "no_benchmark" if human is None else status_for(gap, pb)
    outcome_gap = (positive["human"] or 0) - (positive["ai"] or 0)
    if status in ("on_par", "ahead") and outcome_gap >= pb.outcome_margin:
        status = "behind"  # similar call quality, but the bot converts clearly fewer calls into next steps
    compared = [p for p in params if p["human"] is not None and p["ai"] is not None]
    counts = {s: sum(1 for p in compared if p["status"] == s) for s in ("behind", "on_par", "ahead")}

    points: list[str] = []
    if ai is not None and human:
        points.append(
            f"The bot averages {ai:.1f} / 5 against {human:.1f} / 5 for human agents "
            f"({round(100 * ai / human)}% of human quality)."
        )
    if compared:
        points.append(
            f"Humans are ahead on {counts['behind']} of {len(compared)} review dimensions, "
            f"on par on {counts['on_par']}, and the bot is ahead on {counts['ahead']}."
        )
    if positive["ai"] is not None and positive["human"] is not None:
        points.append(
            "Calls ending with a concrete next step (sale, store visit, callback or other agreed step): "
            f"bot {positive['ai']}%, humans {positive['human']}%."
        )
    behind = sorted((p for p in compared if p["status"] == "behind"), key=lambda p: -p["gap"])[:3]
    if behind:
        points.append("Biggest gaps: " + ", ".join(f"{p['label']} (−{p['gap']:.1f})" for p in behind) + ".")
    if causes:
        top = causes[0]
        points.append(
            f"Most common bot failure: {top['label']} — in {top['count']} of {top['of']} bot calls."
        )

    return {
        "status": status,
        "label": VERDICT_LABELS[status],
        "gap": gap,
        "readiness_pct": round(100 * ai / human) if ai is not None and human else None,
        "dimensions_behind": counts["behind"],
        "dimensions_on_par": counts["on_par"],
        "dimensions_ahead": counts["ahead"],
        "positive_outcome_pct": positive,
        "top_levers": [p["label"] for p in params if p["priority"] in ("high", "medium")][:3],
        "points": points,
    }


def build_improvement(
    done: dict[str, list[Call]], analyses: dict[int, Analysis], scores: dict[str, Any]
) -> dict[str, Any]:
    pb = get_business().playbook
    res: Results = {c.id: analyses[c.id].result for side in SIDES for c in done[side]}  # type: ignore[index]
    params = _parameters(done, res, pb)
    causes = root_causes(done["ai"], res, pb)
    positive = {side: _positive_pct(done[side], res) for side in SIDES}
    return {
        "verdict": _verdict(scores, params, causes, positive, pb),
        "parameters": params,
        "root_causes": causes,
        "objections": objections(done, res),
        "call_rca": call_rca(done["ai"], res, pb),
    }
