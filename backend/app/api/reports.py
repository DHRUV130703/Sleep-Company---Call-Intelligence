"""Saved report files (PDF, Word, Excel, CSV, JSON) and their public download links.

GET /api/reports                         list saved reports, newest first (with their links)
GET /api/reports/<token>/<filename>      public download — anyone with the link can open it
"""

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlmodel import Session, col, select

from app import storage
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models import SavedReport
from app.pipeline.saved_reports import report_row

router = APIRouter(tags=["reports"])


@router.get("/reports")
def list_reports(limit: int = 100, session: Session = Depends(get_session)) -> dict:
    rows = session.exec(select(SavedReport).order_by(col(SavedReport.id).desc()).limit(min(limit, 500))).all()
    return {"reports": [report_row(r) for r in rows]}


@router.get("/reports/{token}/{filename}")
def download_report(token: str, filename: str, session: Session = Depends(get_session)) -> Response:
    report = session.exec(select(SavedReport).where(SavedReport.token == token)).first()
    if report is None or report.filename != filename or not storage.exists(report.storage_key):
        raise AppError(ErrorCode.NOT_FOUND, "This report link is not valid (or the report was deleted).")
    # PDF and JSON open in the browser; Word, Excel and CSV download.
    disposition = "inline" if report.format in ("pdf", "json") else "attachment"
    return Response(
        storage.read_bytes(report.storage_key),
        media_type=report.content_type,
        headers={"Content-Disposition": f'{disposition}; filename="{report.filename}"'},
    )
