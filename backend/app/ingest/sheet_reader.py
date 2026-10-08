"""Spreadsheets of recording links (.xlsx, .xls, .csv): read, suggest a column mapping, validate rows.

Flow: read_table() → suggest_mapping(headers) → (user confirms in the UI) → rows_to_specs(rows, mapping)
"""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.errors import AppError, ErrorCode

# field → header words that suggest it (PRD §6.1.2). Order matters: first match wins.
FIELD_HINTS: dict[str, list[str]] = {
    "recording_url": ["recording_url", "recording", "url", "link", "audio", "mp4", "mp3", "file"],
    "agent_type": ["agent_type", "agent type", "caller type", "bot/human", "type", "channel"],
    "lead_name": ["customer_name", "customer name", "lead_name", "lead name", "customer", "name", "lead"],
    "lead_phone": ["phone", "mobile", "number", "contact", "msisdn"],
    "call_datetime": ["call_datetime", "datetime", "date", "time", "called_at", "created"],
    "agent_name": ["agent_name", "agent name", "agent", "owner", "store", "executive", "caller"],
    "campaign": ["campaign", "purpose", "source"],
    "external_id": ["external_id", "call_id", "crm_id", "id"],
}
FIELDS = list(FIELD_HINTS)

AI_WORDS = {
    "ai",
    "bot",
    "voicebot",
    "voice bot",
    "ai bot",
    "ai voice bot",
    "ivr",
    "virtual",
    "machine",
    "robot",
}
HUMAN_WORDS = {"human", "agent", "person", "store", "executive", "caller", "manual", "tele", "telecaller"}


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (headers, rows). Every value is a trimmed string."""
    ext = path.suffix.lower()
    try:
        if ext == ".csv":
            matrix = _read_csv(path)
        elif ext == ".xlsx":
            matrix = _read_xlsx(path)
        elif ext == ".xls":
            matrix = _read_xls(path)
        else:
            raise AppError(ErrorCode.BAD_SHEET, "Use a .xlsx, .xls or .csv file.")
    except AppError:
        raise
    except Exception as exc:
        raise AppError(ErrorCode.BAD_SHEET, detail={"reason": str(exc)[:200]}) from exc

    matrix = [r for r in matrix if any(c.strip() for c in r)]
    if not matrix:
        raise AppError(ErrorCode.BAD_SHEET, "The spreadsheet is empty.")
    headers = _unique_headers(matrix[0])
    rows = [{h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(headers)} for r in matrix[1:]]
    return headers, rows


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="minutes")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))  # phone numbers stored as numbers
    return str(v)


def _read_csv(path: Path) -> list[list[str]]:
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    # Detect only the delimiter. Quote rules stay standard ("…"): exports often contain single quotes
    # ('+91-98…' or URLs like data={'id':'1'}) that would fool a quote-character guess.
    try:
        delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    return [list(r) for r in csv.reader(io.StringIO(text), delimiter=delimiter)]


def _read_xlsx(path: Path) -> list[list[str]]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = [[_cell(v) for v in row] for row in ws.iter_rows(values_only=True)]
    wb.close()
    return rows


def _read_xls(path: Path) -> list[list[str]]:
    import xlrd

    sheet = xlrd.open_workbook(str(path)).sheet_by_index(0)
    return [[_cell(sheet.cell_value(r, c)) for c in range(sheet.ncols)] for r in range(sheet.nrows)]


def _unique_headers(raw: list[str]) -> list[str]:
    out: list[str] = []
    for i, h in enumerate(raw):
        name = h.strip() or f"Column {i + 1}"
        base, n = name, 2
        while name in out:
            name, n = f"{base} ({n})", n + 1
        out.append(name)
    return out


def suggest_mapping(headers: list[str], rows: list[dict[str, str]] | None = None) -> dict[str, str | None]:
    """Guess which column holds which field. Unknown → None."""
    norm = {h: re.sub(r"[\s\-]+", " ", h.lower()).strip() for h in headers}
    used: set[str] = set()
    mapping: dict[str, str | None] = {}
    for fld, hints in FIELD_HINTS.items():
        choice = None
        for hint in hints:
            for h in headers:
                if h in used:
                    continue
                n = norm[h]
                if n == hint or n.replace(" ", "_") == hint or (len(hint) > 3 and hint in n):
                    choice = h
                    break
            if choice:
                break
        mapping[fld] = choice
        if choice:
            used.add(choice)
    # If no header looks like a URL column, pick the column whose values look like links.
    if not mapping["recording_url"] and rows:
        for h in headers:
            if h not in used and sum(_is_url(r.get(h, "")) for r in rows[:20]) >= 1:
                mapping["recording_url"] = h
                break
    return mapping


def _is_url(v: str) -> bool:
    p = urlparse(v.strip())
    return p.scheme in ("http", "https") and bool(p.netloc)


def normalise_agent_type(value: str) -> str | None:
    v = re.sub(r"[_\-]+", " ", value.strip().lower())
    if not v:
        return None
    if v in AI_WORDS or "bot" in v or v.startswith("ai"):
        return "ai"
    if v in HUMAN_WORDS or "human" in v:
        return "human"
    return None


@dataclass
class CallSpec:
    """One call to create, from a sheet row, a pasted link, a file or a ZIP entry."""

    label: str
    agent_type: str  # "ai" | "human"
    source_url: str | None = None
    file_path: str | None = None
    upload_id: str | None = None
    lead_name: str = ""
    lead_phone: str = ""
    call_datetime: str = ""
    agent_name: str = ""
    campaign: str = ""
    external_id: str = ""


@dataclass
class SheetCheck:
    specs: list[CallSpec] = field(default_factory=list)
    problems: list[dict[str, Any]] = field(default_factory=list)  # {row, message}
    duplicates: int = 0
    total_rows: int = 0


def rows_to_specs(
    rows: list[dict[str, str]],
    mapping: dict[str, str | None],
    agent_type_mode: str,
    *,
    require_url: bool = True,
) -> SheetCheck:
    """Validate rows. Row numbers in problems match the spreadsheet (header = row 1)."""
    check = SheetCheck(total_rows=len(rows))
    seen: set[str] = set()

    def get(row: dict[str, str], fld: str) -> str:
        col = mapping.get(fld)
        return row.get(col, "").strip() if col else ""

    for n, row in enumerate(rows, start=2):
        url = get(row, "recording_url")
        if require_url and not _is_url(url):
            check.problems.append({"row": n, "message": "Missing or invalid link" if url else "No link"})
            continue
        key = url.lower()
        if key in seen:
            check.duplicates += 1
            continue
        seen.add(key)

        if agent_type_mode in ("ai", "human"):
            agent_type = agent_type_mode
        else:
            raw = get(row, "agent_type")
            agent_type = normalise_agent_type(raw) or ""
            if not agent_type:
                check.problems.append({"row": n, "message": f"Unknown agent type '{raw}' (use AI or Human)"})
                continue

        name = get(row, "lead_name")
        ext_id = get(row, "external_id")
        phone = get(row, "lead_phone").strip("'\"` ")
        url_stem = Path(urlparse(url).path).stem
        generic = url_stem.lower() in ("", "command", "download", "file", "recording", "index")
        label = ext_id or name or phone or (url_stem if not generic else "") or f"Row {n}"
        check.specs.append(
            CallSpec(
                label=label[:120],
                agent_type=agent_type,
                source_url=url or None,
                lead_name=name,
                lead_phone=get(row, "lead_phone"),
                call_datetime=get(row, "call_datetime"),
                agent_name=get(row, "agent_name"),
                campaign=get(row, "campaign"),
                external_id=ext_id,
            )
        )
    return check
