"""Keep the AI honest: verify quotes against the transcript, and resolve "kal" / "tomorrow" into dates.

- verify_quote(): a quote counts only if it (fuzzily) appears in the transcript.
- locate_quote(): which segment a quote came from, so we can jump to its timestamp.
- resolve_when(): turns what was said ("kal shaam", "Monday", "8 Oct") into a calendar date.
"""

import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from rapidfuzz import fuzz

QUOTE_MATCH_MIN = 90  # 0–100 similarity needed for a quote to count as verified
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def _norm(text: str) -> str:
    return " ".join(_PUNCT.sub(" ", text.lower()).split())


def verify_quote(quote: str, transcript_text: str) -> bool:
    q = _norm(quote)
    if len(q) < 3:
        return False
    return fuzz.partial_ratio(q, _norm(transcript_text)) >= QUOTE_MATCH_MIN


def locate_quote(quote: str, segments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Best-matching segment for a quote (or None if nothing matches well)."""
    q = _norm(quote)
    if len(q) < 3:
        return None
    best, best_score = None, 0.0
    for s in segments:
        score = fuzz.partial_ratio(q, _norm(s["text"]))
        if score > best_score:
            best, best_score = s, score
    return best if best_score >= QUOTE_MATCH_MIN else None


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

WEEKDAYS = {
    "monday": 0, "somvar": 0, "somwar": 0, "सोमवार": 0,
    "tuesday": 1, "mangalvar": 1, "mangalwar": 1, "मंगलवार": 1,
    "wednesday": 2, "budhvar": 2, "budhwar": 2, "बुधवार": 2,
    "thursday": 3, "guruvar": 3, "guruwar": 3, "brihaspativar": 3, "गुरुवार": 3,
    "friday": 4, "shukravar": 4, "shukrawar": 4, "शुक्रवार": 4,
    "saturday": 5, "shanivar": 5, "shaniwar": 5, "शनिवार": 5,
    "sunday": 6, "ravivar": 6, "raviwar": 6, "itvaar": 6, "रविवार": 6,
}  # fmt: skip
MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
    )
}

_RULES: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"\b(day after tomorrow|parso|parson|परसों)\b"), 2),
    (re.compile(r"\b(tomorrow|tmrw|kal|कल)\b"), 1),
    (re.compile(r"\b(today|tonight|aaj|abhi|आज)\b"), 0),
    (re.compile(r"\b(next week|agle hafte|अगले हफ्ते)\b"), 7),
]


def resolve_when(phrase: str, call_dt: datetime | None, tz: str = "Asia/Kolkata") -> date | None:
    """'kal shaam 6 baje' + call on 7 Oct → 8 Oct. Returns None if no date can be worked out."""
    if not phrase or not phrase.strip():
        return None
    text = phrase.lower()
    base = (call_dt or datetime.now(ZoneInfo(tz))).astimezone(ZoneInfo(tz)).date()

    if m := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text):
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    if m := re.search(r"\bin (\d{1,2}) days?\b", text):
        return base + timedelta(days=int(m[1]))
    for pattern, days in _RULES:
        if pattern.search(text):
            return base + timedelta(days=days)
    for name, wd in WEEKDAYS.items():
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text):
            ahead = (wd - base.weekday()) % 7 or 7
            return base + timedelta(days=ahead)
    if m := re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3})[a-z]*\b", text):
        month = MONTHS.get(m[2])
        if month:
            try:
                d = date(base.year, month, int(m[1]))
            except ValueError:
                return None
            return d if d >= base else date(base.year + 1, month, int(m[1]))
    return None
