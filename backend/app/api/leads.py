"""All Conversations (leads list + KPIs) and Lead Details (PRD §6.3, §6.4)."""

from collections import Counter
from datetime import date, datetime
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.api.views import call_row, iso, lead_row
from app.config import get_settings
from app.db import get_session, utcnow
from app.errors import AppError, ErrorCode
from app.models import (
    Action,
    ActionSource,
    Analysis,
    Batch,
    Call,
    CallMetrics,
    CallStatus,
    Lead,
    LeadStatus,
    Note,
)
from app.pipeline.leads import status_category

router = APIRouter(tags=["leads"])

INTENT_BUCKETS = ["high", "moderate", "neutral", "low", "not_qualified", "not_available"]


class LeadFilters(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    q: str = ""
    batch_ids: list[int] = []  # one or more upload batches ("source")
    campaign: str = ""
    owner: str = ""
    agent_type: str = ""
    status: LeadStatus | None = None
    status_category: str = ""
    intent_bucket: str = ""


def _filters(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str = "",
    batch_id: str = "",  # one id, or several separated by commas: "3,5,8"
    campaign: str = "",
    owner: str = "",
    agent_type: str = "",
    status: LeadStatus | None = None,
    status_category: str = "",
    intent_bucket: str = "",
) -> LeadFilters:
    tz = ZoneInfo(get_settings().default_timezone)
    # Dates without a timezone are read as local (IST) time.
    if date_from and date_from.tzinfo is None:
        date_from = date_from.replace(tzinfo=tz)
    if date_to and date_to.tzinfo is None:
        date_to = date_to.replace(tzinfo=tz)
    return LeadFilters(
        date_from=date_from,
        date_to=date_to,
        q=q,
        batch_ids=sorted({int(x) for x in batch_id.split(",") if x.strip().isdigit()}),
        campaign=campaign,
        owner=owner,
        agent_type=agent_type,
        status=status,
        status_category=status_category,
        intent_bucket=intent_bucket,
    )


def _call_filters(f: LeadFilters) -> list[Any]:
    out: list[Any] = []
    if f.batch_ids:
        out.append(col(Call.batch_id).in_(f.batch_ids))
    if f.campaign:
        out.append(Call.campaign == f.campaign)
    if f.owner:
        out.append(Call.agent_name == f.owner)
    if f.agent_type in ("ai", "human"):
        out.append(Call.agent_type == f.agent_type)
    return out


def _leads(
    session: Session, f: LeadFilters, *, skip_intent: bool = False, skip_status: bool = False
) -> list[Lead]:
    stmt = select(Lead)
    if call_f := _call_filters(f):
        stmt = stmt.where(col(Lead.id).in_(select(Call.lead_id).where(*call_f)))
    if f.date_from:
        stmt = stmt.where(col(Lead.last_call_at) >= f.date_from)
    if f.date_to:
        stmt = stmt.where(col(Lead.last_call_at) <= f.date_to)
    if f.q.strip():
        like = f"%{f.q.strip()}%"
        digits = "".join(ch for ch in f.q if ch.isdigit())
        conds = [col(Lead.name).ilike(like)]
        if len(digits) >= 3:
            conds.append(col(Lead.phone_e164).ilike(f"%{digits}%"))
        stmt = stmt.where(or_(*conds))
    if f.status and not skip_status:
        stmt = stmt.where(Lead.status == f.status)
    leads = list(session.exec(stmt).all())
    if f.status_category and not skip_status:
        leads = [ld for ld in leads if status_category(ld.status) == f.status_category]
    if f.intent_bucket and not skip_intent:
        leads = [ld for ld in leads if ld.intent_bucket == f.intent_bucket]
    return leads


def _next_tasks(session: Session, lead_ids: list[int]) -> dict[int, Action]:
    actions = session.exec(
        select(Action).where(col(Action.lead_id).in_(lead_ids), Action.done == False)  # noqa: E712
    ).all()
    best: dict[int, Action] = {}
    for a in actions:
        cur = best.get(a.lead_id)
        key = (a.due_date is None, a.due_date or date.max, a.id)
        if cur is None or key < (cur.due_date is None, cur.due_date or date.max, cur.id):
            best[a.lead_id] = a
    return best


@router.get("/leads")
def list_leads(
    f: LeadFilters = Depends(_filters),
    sort: str = "last_call",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict:
    leads = _leads(session, f)
    keys = {
        "last_call": lambda ld: (ld.last_call_at is not None, ld.last_call_at or datetime.min),
        "intent": lambda ld: (ld.intent_score is not None, ld.intent_score or 0),
        "name": lambda ld: (ld.name or "~").lower(),
    }
    leads.sort(key=keys.get(sort, keys["last_call"]), reverse=sort != "name")
    total = len(leads)
    page_items = leads[(page - 1) * page_size : page * page_size]
    ids = [ld.id for ld in page_items if ld.id is not None]

    calls = session.exec(select(Call).where(col(Call.lead_id).in_(ids))).all()
    per_lead: dict[int, list[Call]] = {}
    for c in calls:
        per_lead.setdefault(c.lead_id or 0, []).append(c)
    tasks = _next_tasks(session, ids)

    items = []
    for ld in page_items:
        cs = per_lead.get(ld.id or 0, [])
        task = tasks.get(ld.id or 0)
        items.append(
            {
                **lead_row(ld),
                "conversations": len(cs),
                "agent_types": sorted({c.agent_type for c in cs}),
                "next_task": {"title": task.title, "due_date": iso_date(task.due_date)} if task else None,
                "processing": any(c.status in (CallStatus.queued, CallStatus.running) for c in cs),
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def iso_date(d: date | None) -> str | None:
    return d.isoformat() if d else None


# ---------------------------------------------------------------------------
# KPIs (header cards) with period-over-period deltas
# ---------------------------------------------------------------------------


def _kpi_values(session: Session, f: LeadFilters) -> dict[str, Any]:
    leads = _leads(session, f, skip_intent=True)
    ids = [ld.id for ld in leads]
    calls = session.exec(select(Call).where(col(Call.lead_id).in_(ids), *_call_filters(f))).all()
    done_ids = [c.id for c in calls if c.status == CallStatus.done]
    analyses = session.exec(select(Analysis).where(col(Analysis.call_id).in_(done_ids))).all()
    metrics = session.exec(select(CallMetrics).where(col(CallMetrics.call_id).in_(done_ids))).all()

    connected = {c.lead_id for c in calls if c.status == CallStatus.done}
    cats = Counter(status_category(ld.status) for ld in leads)
    buckets = Counter(ld.intent_bucket for ld in leads if ld.intent_bucket)
    talk = [
        float(m.data["talk_listen_agent_pct"])
        for m in metrics
        if m.data.get("talk_listen_agent_pct") is not None
    ]
    quality = [a.quality_pct for a in analyses if a.quality_pct is not None]
    n = len(leads)
    return {
        "conversations": len(calls),
        "audio_seconds": round(sum(c.duration_s or 0 for c in calls), 1),
        "detailed_pct": round(100 * sum(1 for m in metrics if m.data.get("is_detailed")) / len(metrics), 1)
        if metrics
        else None,
        "talk_listen_agent_pct": round(mean(talk)) if talk else None,
        "quality_pct": round(mean(quality), 2) if quality else None,
        "total_leads": n,
        "connected_leads": len(connected),
        "not_connected_leads": n - len(connected),
        "won": cats["won"],
        "lost": cats["lost"],
        "in_progress": cats["in_progress"],
        "intent": {b: buckets.get(b, 0) for b in INTENT_BUCKETS},
    }


def _delta(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or prev == 0:
        return None
    return round(100 * (cur - prev) / prev, 1)


@router.get("/leads/kpis")
def lead_kpis(f: LeadFilters = Depends(_filters), session: Session = Depends(get_session)) -> dict:
    cur = _kpi_values(session, f)
    prev = None
    if f.date_from and f.date_to:
        span = f.date_to - f.date_from
        prev_f = f.model_copy(update={"date_from": f.date_from - span, "date_to": f.date_from})
        prev = _kpi_values(session, prev_f)
    deltas: dict[str, Any] = {}
    if prev:
        for k in (
            "total_leads",
            "connected_leads",
            "not_connected_leads",
            "won",
            "lost",
            "in_progress",
            "conversations",
        ):
            deltas[k] = _delta(cur[k], prev[k])
        deltas["intent"] = {b: _delta(cur["intent"][b], prev["intent"][b]) for b in INTENT_BUCKETS}
    return {**cur, "deltas": deltas, "has_previous_period": prev is not None}


@router.get("/leads/filters")
def filter_options(session: Session = Depends(get_session)) -> dict:
    owners = sorted({o for o in session.exec(select(Call.agent_name).distinct()).all() if o})
    campaigns = sorted({c for c in session.exec(select(Call.campaign).distinct()).all() if c})
    batches = [
        {"id": b.id, "name": b.name} for b in session.exec(select(Batch).order_by(col(Batch.id).desc()))
    ]
    return {
        "owners": owners,
        "campaigns": campaigns,
        "batches": batches,
        "statuses": [s.value for s in LeadStatus],
        "intent_buckets": INTENT_BUCKETS,
    }


# ---------------------------------------------------------------------------
# Lead details
# ---------------------------------------------------------------------------


def _get_lead(session: Session, lead_id: int) -> Lead:
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise AppError(ErrorCode.NOT_FOUND, "Lead not found.")
    return lead


@router.get("/leads/{lead_id}")
def lead_detail(lead_id: int, session: Session = Depends(get_session)) -> dict:
    lead = _get_lead(session, lead_id)
    calls = sorted(
        session.exec(select(Call).where(Call.lead_id == lead_id)).all(),
        key=lambda c: c.call_datetime or c.created_at,
    )
    ids = [c.id for c in calls]
    analyses = {a.call_id: a for a in session.exec(select(Analysis).where(col(Analysis.call_id).in_(ids)))}
    metrics = {
        m.call_id: m.data for m in session.exec(select(CallMetrics).where(col(CallMetrics.call_id).in_(ids)))
    }

    analysed = [c for c in calls if c.id in analyses]
    latest = analyses[analysed[-1].id].result if analysed else None  # type: ignore[index]
    objections = [
        {**o, "call_id": c.id, "call_label": c.label}
        for c in analysed
        for o in analyses[c.id].result.get("objections", [])  # type: ignore[index]
    ]
    talk = [
        m["talk_listen_agent_pct"] for m in metrics.values() if m.get("talk_listen_agent_pct") is not None
    ]
    quality = [a.quality_pct for a in analyses.values() if a.quality_pct is not None]
    actions = session.exec(select(Action).where(Action.lead_id == lead_id).order_by(col(Action.id))).all()
    notes = session.exec(select(Note).where(Note.lead_id == lead_id).order_by(col(Note.id).desc())).all()

    return {
        **lead_row(lead),
        "stats": {
            "total_duration_s": round(sum(c.duration_s or 0 for c in calls), 1),
            "talk_listen_agent_pct": round(mean(talk)) if talk else None,
            "intent_score": lead.intent_score,
            "avg_quality_pct": round(mean(quality), 1) if quality else None,
        },
        "calls": [
            {
                **call_row(c, analyses.get(c.id or 0)),
                "summary": (
                    analyses[c.id].result.get("summary")  # type: ignore[index]
                    if c.id in analyses
                    else None
                ),
            }
            for c in reversed(calls)
        ],
        "insights": {
            "intent": latest["intent"] if latest else None,
            "bant": latest["bant"] if latest else None,
            "mood": latest["mood"] if latest else None,
            "customer": latest["customer"] if latest else None,
            "outcome": latest["outcome"] if latest else None,
            "unanswered_questions": latest.get("unanswered_questions", []) if latest else [],
            "objections": objections,
        },
        "path": lead.path_summary,
        "actions": [_action_json(a) for a in actions],
        "notes": [{"id": n.id, "body": n.body, "created_at": iso(n.created_at)} for n in notes],
        "statuses": [s.value for s in LeadStatus],
    }


class LeadPatch(BaseModel):
    status: LeadStatus | None = None
    assignee: str | None = None


@router.patch("/leads/{lead_id}")
def patch_lead(lead_id: int, body: LeadPatch, session: Session = Depends(get_session)) -> dict:
    lead = _get_lead(session, lead_id)
    if body.status is not None:
        lead.status, lead.status_overridden = body.status, True
    if body.assignee is not None:
        lead.assignee = body.assignee.strip()
    lead.updated_at = utcnow()
    session.add(lead)
    session.commit()
    return lead_row(lead)


# ---------------------------------------------------------------------------
# Actions (tasks) and notes
# ---------------------------------------------------------------------------


def _action_json(a: Action) -> dict[str, Any]:
    return {
        "id": a.id,
        "call_id": a.call_id,
        "title": a.title,
        "say": a.say,
        "why": a.why,
        "due_date": iso_date(a.due_date),
        "done": a.done,
        "source": a.source,
    }


class ActionBody(BaseModel):
    title: str | None = None
    due_date: date | None = None
    done: bool | None = None


@router.post("/leads/{lead_id}/actions")
def add_action(lead_id: int, body: ActionBody, session: Session = Depends(get_session)) -> dict:
    _get_lead(session, lead_id)
    if not (body.title or "").strip():
        raise AppError(ErrorCode.VALIDATION_ERROR, "A task needs a title.")
    a = Action(
        lead_id=lead_id, title=(body.title or "").strip(), due_date=body.due_date, source=ActionSource.manual
    )
    session.add(a)
    session.commit()
    session.refresh(a)
    return _action_json(a)


@router.patch("/actions/{action_id}")
def update_action(action_id: int, body: ActionBody, session: Session = Depends(get_session)) -> dict:
    a = session.get(Action, action_id)
    if a is None:
        raise AppError(ErrorCode.NOT_FOUND, "Task not found.")
    data = body.model_dump(exclude_unset=True)
    if "title" in data and data["title"]:
        a.title = data["title"].strip()
    if "due_date" in data:
        a.due_date = data["due_date"]
    if "done" in data and data["done"] is not None:
        a.done = data["done"]
    session.add(a)
    session.commit()
    return _action_json(a)


@router.delete("/actions/{action_id}")
def delete_action(action_id: int, session: Session = Depends(get_session)) -> dict:
    a = session.get(Action, action_id)
    if a:
        session.delete(a)
        session.commit()
    return {"ok": True}


class NoteBody(BaseModel):
    body: str


@router.post("/leads/{lead_id}/notes")
def add_note(lead_id: int, body: NoteBody, session: Session = Depends(get_session)) -> dict:
    _get_lead(session, lead_id)
    if not body.body.strip():
        raise AppError(ErrorCode.VALIDATION_ERROR, "The note is empty.")
    n = Note(lead_id=lead_id, body=body.body.strip())
    session.add(n)
    session.commit()
    session.refresh(n)
    return {"id": n.id, "body": n.body, "created_at": iso(n.created_at)}


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, session: Session = Depends(get_session)) -> dict:
    n = session.get(Note, note_id)
    if n:
        session.delete(n)
        session.commit()
    return {"ok": True}
