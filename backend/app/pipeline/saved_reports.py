"""Saved report files: every AI vs Human report you download is also stored, with a public link.

    save_report(session, scope, result, "pdf")  → SavedReport (file in storage + row in `reports`)

The same report (same calls, same build of the comparison) in the same format is made only once; later
downloads reuse the stored file. Public link: <PUBLIC_BASE_URL>/api/reports/<token>/<filename>.
"""

import csv
import io
import json
import secrets
from typing import Any

from sqlmodel import Session, select

from app import storage
from app.config import get_settings
from app.models import SavedReport
from app.pipeline.compare import export_rows, scope_key
from app.pipeline.report import build_outline
from app.pipeline.report_docx import render_docx
from app.pipeline.report_pdf import render_pdf
from app.pipeline.report_xlsx import render_xlsx

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
    "json": "application/json",
}
FORMATS = tuple(CONTENT_TYPES)


def base_url() -> str:
    s = get_settings()
    return (s.public_base_url or s.frontend_origin).rstrip("/")


def public_url(token: str, filename: str) -> str:
    return f"{base_url()}/api/reports/{token}/{filename}"


def render(fmt: str, result: dict[str, Any], session: Session) -> bytes:
    if fmt == "pdf":
        return render_pdf(build_outline(result), base_url())
    if fmt == "docx":
        return render_docx(build_outline(result))
    if fmt == "xlsx":
        return render_xlsx(result, export_rows(result, session))
    if fmt == "json":
        return json.dumps(result, ensure_ascii=False, indent=2).encode()
    if fmt == "csv":
        rows = export_rows(result, session)
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return ("﻿" + buf.getvalue()).encode()  # BOM: Excel then reads Hindi text correctly
    raise ValueError(f"unknown report format: {fmt}")


def filename_for(result: dict[str, Any], fmt: str) -> str:
    name = "ai-vs-human-scores" if fmt == "csv" else "ai-vs-human-report"
    return f"{name}-{str(result.get('generated_at', ''))[:10]}.{fmt}"


def save_report(session: Session, scope: dict[str, Any], result: dict[str, Any], fmt: str) -> SavedReport:
    if fmt not in CONTENT_TYPES:
        raise ValueError(f"unknown report format: {fmt}")
    built_at = str(result.get("generated_at", ""))
    existing = session.exec(
        select(SavedReport).where(
            SavedReport.scope_hash == scope_key(scope),
            SavedReport.report_built_at == built_at,
            SavedReport.format == fmt,
        )
    ).first()
    if existing and storage.exists(existing.storage_key):
        return existing

    data = render(fmt, result, session)
    token = secrets.token_urlsafe(18)
    filename = filename_for(result, fmt)
    key = f"reports/{token}/{filename}"
    storage.put_bytes(key, data, CONTENT_TYPES[fmt])
    report = SavedReport(
        token=token,
        format=fmt,
        filename=filename,
        content_type=CONTENT_TYPES[fmt],
        size=len(data),
        storage_key=key,
        url=public_url(token, filename),
        scope=scope,
        scope_hash=scope_key(scope),
        report_built_at=built_at,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def report_row(r: SavedReport) -> dict[str, Any]:
    return {
        "id": r.id,
        "format": r.format,
        "filename": r.filename,
        "size": r.size,
        "url": r.url,
        "scope": r.scope,
        "report_built_at": r.report_built_at,
        "created_at": r.created_at.isoformat(),
    }
