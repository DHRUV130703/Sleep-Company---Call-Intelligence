"""Read call details from dialer recording file names.

Ameyo (and similar dialers) name recordings like:
    madiha_chougle_thesleepcompany_in__Sales_Outbound__435__-1__9894020300__2026-10-06_20-41-49.mp3
    └── agent (from their login email) ──┘ └─ campaign ─┘              └ phone ┘ └── date and time ──┘

parse() returns whatever it can find; every field is optional.
"""

import contextlib
import re
from datetime import datetime
from pathlib import PurePosixPath
from zoneinfo import ZoneInfo

_DATETIME = re.compile(r"(\d{4}-\d{2}-\d{2})[_ T](\d{2})[-:](\d{2})[-:](\d{2})")
_TLDS = {"in", "com", "co", "net", "org", "io"}


def _agent_from_login(token: str) -> str:
    """ "madiha_chougle_thesleepcompany_in" → "Madiha Chougle" (drops the email domain)."""
    parts = [p for p in token.split("_") if p]
    if len(parts) >= 3 and parts[-1].lower() in _TLDS:
        parts = parts[:-2]  # drop "<company>_<tld>"
    return " ".join(p.capitalize() for p in parts)


def parse(filename: str, tz: str = "Asia/Kolkata") -> dict[str, object]:
    stem = PurePosixPath(filename).stem
    out: dict[str, object] = {}
    if m := _DATETIME.search(stem):
        with contextlib.suppress(ValueError):  # e.g. 2026-13-45 → just skip the date
            out["call_datetime"] = datetime.strptime(
                f"{m[1]} {m[2]}:{m[3]}:{m[4]}", "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=ZoneInfo(tz))
    fields = stem.split("__")
    if len(fields) >= 4:  # dialer pattern: agent__campaign__…__phone__datetime
        if agent := _agent_from_login(fields[0]):
            out["agent_name"] = agent
        if fields[1].strip("_"):
            out["campaign"] = fields[1].replace("_", " ").strip()
        for f in fields[2:]:
            if re.fullmatch(r"\+?\d{10,13}", f):
                out["phone"] = f
    return out
