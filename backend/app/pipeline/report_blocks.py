"""Building blocks of the shareable AI vs Human report, shared by report.py and report_improvement.py.

Block types:  Para(text, muted)  ·  Sub(text)  ·  Bullets(items)  ·  Table(headers, rows)  ·  Quote(text, source, href)
"""

from dataclasses import dataclass, field

SIDES = (("ai", "AI voice bot"), ("human", "Human agents"))


@dataclass
class Para:
    text: str
    muted: bool = False


@dataclass
class Sub:
    """A small heading inside a section."""

    text: str


@dataclass
class Bullets:
    items: list[str]


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]


@dataclass
class Quote:
    text: str
    source: str  # e.g. "Human agents · +91-9284201609 · 0:42"
    href: str = ""  # link to the call at that moment (used by the print page)


Block = Para | Sub | Bullets | Table | Quote


@dataclass
class Section:
    heading: str
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Report:
    title: str
    meta: list[str]
    sections: list[Section]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def clock(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    s = int(round(seconds))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def hours_mins(seconds: float) -> str:
    m = int(seconds // 60)
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min"


def num(v: float | None, suffix: str = "") -> str:
    if v is None:
        return "—"
    return f"{v:g}{suffix}" if isinstance(v, int) or float(v).is_integer() else f"{v:.1f}{suffix}"


def humanize(key: str) -> str:
    s = key.replace("_", " ")
    return s[:1].upper() + s[1:]


def call_href(call_id: int, t: float | None) -> str:
    """App link to a call at a moment (relative, so it works wherever the app is served)."""
    return f"/calls/{call_id}?t={max(0, int(t or 0))}"
