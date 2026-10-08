"""Measured metrics (PRD §7.2): counted from who said what. Pure functions, no AI.

Input: transcript segments [{"role": "agent"|"customer", "start", "end", "text"}, ...]
"""

import re
from typing import Any

# English and Hindi (Roman + Devanagari) question words.
QUESTION_WORDS = {
    "what", "why", "how", "when", "where", "which", "who", "whom", "whose", "can", "could", "would", "will",
    "do", "does", "did", "is", "are", "shall", "should", "may",
    "kya", "kyun", "kyon", "kaise", "kab", "kahan", "kaun", "kitna", "kitne", "kitni", "konsa", "kaunsa",
    "क्या", "क्यों", "कैसे", "कब", "कहाँ", "कौन", "कितना", "कितने", "कितनी",
}  # fmt: skip

# \w alone splits Hindi words at their vowel signs (ा ि े …), so include the whole Devanagari block.
_WORD = re.compile(r"[\w\u0900-\u097F']+", re.UNICODE)
_SENTENCE = re.compile(r"[^.!?।]+[.!?।]?")

DETAILED_MIN_S = 120
DETAILED_MIN_TURNS = 6
INTERRUPT_OVERLAP_S = 0.3


def words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _normalise(text: str) -> str:
    return " ".join(words(text))


def count_questions(text: str) -> int:
    n = 0
    for sentence in _SENTENCE.findall(text):
        s = sentence.strip()
        if not s:
            continue
        w = words(s)
        if s.endswith("?") or (w and w[0] in QUESTION_WORDS and len(w) > 1):
            n += 1
    return n


def turns(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive segments by the same role into one turn."""
    out: list[dict[str, Any]] = []
    for s in segments:
        if out and out[-1]["role"] == s["role"]:
            out[-1]["text"] += " " + s["text"]
            out[-1]["end"] = s["end"]
        else:
            out.append({"role": s["role"], "start": s["start"], "end": s["end"], "text": s["text"]})
    return out


def compute_metrics(segments: list[dict[str, Any]], duration_s: float) -> dict[str, Any]:
    segs = [s for s in segments if s.get("role") in ("agent", "customer") and s.get("text", "").strip()]
    t = turns(segs)
    agent_turns = [x for x in t if x["role"] == "agent"]
    cust_turns = [x for x in t if x["role"] == "customer"]

    def speech(role: str) -> float:
        return sum(max(0.0, s["end"] - s["start"]) for s in segs if s["role"] == role)

    agent_s, cust_s = speech("agent"), speech("customer")
    agent_words = sum(len(words(x["text"])) for x in agent_turns)
    cust_words = sum(len(words(x["text"])) for x in cust_turns)
    total_words = agent_words + cust_words
    minutes = max(duration_s, 1) / 60

    # Agent lines (≥ 4 words) repeated word for word.
    seen: set[str] = set()
    repeats = 0
    for s in segs:
        if s["role"] != "agent":
            continue
        norm = _normalise(s["text"])
        if len(norm.split()) < 4:
            continue
        if norm in seen:
            repeats += 1
        seen.add(norm)

    interruptions = sum(
        1
        for prev, cur in zip(segs, segs[1:], strict=False)
        if cur["role"] != prev["role"] and prev["end"] - cur["start"] > INTERRUPT_OVERLAP_S
    )
    talk_total = agent_s + cust_s
    agent_pct = round(100 * agent_s / talk_total) if talk_total else 0

    return {
        "duration_s": round(duration_s, 1),
        "talk_listen_agent_pct": agent_pct,
        "talk_listen_customer_pct": 100 - agent_pct if talk_total else 0,
        "agent_share_of_words_pct": round(100 * agent_words / total_words, 1) if total_words else 0,
        "words_per_agent_turn": round(agent_words / len(agent_turns), 1) if agent_turns else 0,
        "words_per_customer_turn": round(cust_words / len(cust_turns), 1) if cust_turns else 0,
        "longest_agent_monologue_words": max((len(words(x["text"])) for x in agent_turns), default=0),
        "questions_by_agent": sum(count_questions(x["text"]) for x in agent_turns),
        "agent_words_per_minute": round(agent_words / (agent_s / 60), 1) if agent_s > 0 else 0,
        "agent_repeated_lines": repeats,
        "customer_short_replies_pct": round(
            100 * sum(1 for x in cust_turns if len(words(x["text"])) <= 3) / len(cust_turns), 1
        )
        if cust_turns
        else 0,  # fmt: skip
        "speaker_changes_per_minute": round(max(len(t) - 1, 0) / minutes, 1),
        "interruptions": interruptions,
        "silence_pct": round(max(0.0, 100 * (1 - min(talk_total, duration_s) / duration_s)), 1)
        if duration_s
        else 0,
        "agent_turns": len(agent_turns),
        "customer_turns": len(cust_turns),
        "is_detailed": duration_s >= DETAILED_MIN_S and len(t) >= DETAILED_MIN_TURNS,
    }


# Metric labels and which direction is "better" — used by the comparison page and CSV export.
METRIC_LABELS: dict[str, str] = {
    "duration_s": "Call length",
    "talk_listen_agent_pct": "Agent talk time %",
    "agent_share_of_words_pct": "Agent share of words %",
    "words_per_agent_turn": "Words per agent turn",
    "words_per_customer_turn": "Words per customer turn",
    "longest_agent_monologue_words": "Longest agent monologue (words)",
    "questions_by_agent": "Questions asked by agent",
    "agent_words_per_minute": "Agent words per minute",
    "agent_repeated_lines": "Agent lines repeated word for word",
    "customer_short_replies_pct": "Customer replies of 3 words or fewer %",
    "speaker_changes_per_minute": "Speaker changes per minute",
    "interruptions": "Interruptions",
    "silence_pct": "Silence %",
}
