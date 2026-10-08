"""AI voice bot vs human agents (PRD §6.6). Same query parameters on every endpoint."""

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.db import get_session
from app.models import Batch, Call
from app.pipeline.compare import build_comparison, cached_comparison, export_rows, parse_scope

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


@router.get("/compare/export.json")
async def export_json(scope: dict = Depends(_scope), session: Session = Depends(get_session)) -> Response:
    result = await _result(session, scope, False)
    return Response(
        json.dumps(result, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="ai-vs-human-results.json"'},
    )
