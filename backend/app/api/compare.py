"""AI voice bot vs human agents (PRD §6.6). Same query parameters on every endpoint."""

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.api.batches import requeue_call
from app.db import get_session
from app.models import Batch, Call, CallStage
from app.pipeline.compare import (
    build_comparison,
    cached_comparison,
    export_rows,
    outdated_bot_calls,
    parse_scope,
)
from app.pipeline.report import build_outline
from app.pipeline.report_docx import render_docx
from app.pipeline.report_html import render_html

router = APIRouter(tags=["compare"])


def _scope(
    batch_ids: str | None = None,
    campaign: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    comparable_only: bool = False,
) -> dict:
    return parse_scope(batch_ids, campaign, date_from, date_to, comparable_only)


async def _result(session: Session, scope: dict, force: bool) -> dict:
    if not force and (cached := cached_comparison(session, scope)):
        return cached
    return await build_comparison(session, scope)


@router.get("/compare")
async def compare(
    scope: dict = Depends(_scope), force: bool = False, session: Session = Depends(get_session)
) -> dict:
    return await _result(session, scope, force)


@router.post("/compare/update-bot-reviews")
def update_bot_reviews(scope: dict = Depends(_scope), session: Session = Depends(get_session)) -> dict:
    """Re-analyse bot calls reviewed with an older prompt, so they get the newest fields (e.g. "better" lines)."""
    calls = outdated_bot_calls(session, scope)
    for c in calls:
        requeue_call(session, c, CallStage.analysing)
    session.commit()
    return {"queued": len(calls)}


@router.get("/compare/options")
def options(session: Session = Depends(get_session)) -> dict:
    """Batches and campaigns to choose from, with how many AI / human calls each has."""
    rows = session.exec(
        select(col(Call.batch_id), col(Call.agent_type), func.count()).group_by(
            col(Call.batch_id), col(Call.agent_type)
        )
    ).all()
    per_batch: dict[int, dict[str, int]] = {}
    for batch_id, agent_type, n in rows:
        per_batch.setdefault(batch_id, {"ai": 0, "human": 0})[agent_type] = n
    batches = [
        {
            "id": b.id,
            "name": b.name,
            "created_at": b.created_at.isoformat(),
            **per_batch.get(b.id or 0, {"ai": 0, "human": 0}),
        }
        for b in session.exec(select(Batch).order_by(col(Batch.id).desc()))
    ]
    campaigns = sorted({c for c in session.exec(select(Call.campaign).distinct()).all() if c})
    return {"batches": batches, "campaigns": campaigns}


@router.get("/compare/export.csv")
async def export_csv(scope: dict = Depends(_scope), session: Session = Depends(get_session)) -> Response:
    result = await _result(session, scope, False)
    rows = export_rows(result, session)
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ai-vs-human-scores.csv"'},
    )


@router.get("/compare/export.docx")
async def export_docx(scope: dict = Depends(_scope), session: Session = Depends(get_session)) -> Response:
    """The full report as a Word document, to share with teams."""
    result = await _result(session, scope, False)
    return Response(
        render_docx(build_outline(result)),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{_report_name(result)}.docx"'},
    )


@router.get("/compare/report.html", response_class=HTMLResponse)
async def report_html(
    scope: dict = Depends(_scope),
    auto_print: bool = Query(False, alias="print"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """The full report as a print-ready page. With ?print=1 the browser's "Save as PDF" dialog opens."""
    result = await _result(session, scope, False)
    return HTMLResponse(render_html(build_outline(result), auto_print=auto_print))


def _report_name(result: dict) -> str:
    return "ai-vs-human-report-" + str(result.get("generated_at", ""))[:10]


@router.get("/compare/export.json")
async def export_json(scope: dict = Depends(_scope), session: Session = Depends(get_session)) -> Response:
    result = await _result(session, scope, False)
    return Response(
        json.dumps(result, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="ai-vs-human-results.json"'},
    )
