"""Ranking rules for the bot improvement plan (hand-checked against config/bot_playbook.yaml defaults)."""

from app.config import BotPlaybook
from app.pipeline.bot_improvement import priority_for, status_for

PB = BotPlaybook()  # high: gap ≥ 1.0 or weak ≥ 60% · medium: gap ≥ 0.5 or weak ≥ 30% · on par: ±0.3


def test_priority_from_gap_or_how_often_the_bot_is_weak():
    assert priority_for(1.2, 0, PB) == "high"  # far behind humans
    assert priority_for(0.1, 60, PB) == "high"  # close on average, but weak in most bot calls
    assert priority_for(0.1, 59, PB) == "medium"
    assert priority_for(0.6, 10, PB) == "medium"
    assert priority_for(0.2, 30, PB) == "medium"
    assert priority_for(0.2, 29, PB) == "low"
    assert priority_for(0.4, 0, PB) == "low"
    assert priority_for(-0.5, 0, PB) == "none"  # bot ahead, never weak
    assert priority_for(None, 0, PB) == "none"  # no bot calls scored


def test_status_uses_the_on_par_margin():
    assert status_for(0.31, PB) == "behind"
    assert status_for(0.3, PB) == "on_par"
    assert status_for(-0.3, PB) == "on_par"
    assert status_for(-0.31, PB) == "ahead"
    assert status_for(None, PB) == "no_data"


def test_verdict_is_behind_when_the_bot_converts_fewer_calls():
    from app.pipeline.bot_improvement import _verdict

    scores = {"ai": {"avg_review": 2.7}, "human": {"avg_review": 3.0}}  # quality within the on-par margin
    v = _verdict(scores, [], [], {"ai": 14, "human": 33}, PB)
    assert v["status"] == "behind" and v["readiness_pct"] == 90
    v = _verdict(scores, [], [], {"ai": 30, "human": 33}, PB)
    assert v["status"] == "on_par"
