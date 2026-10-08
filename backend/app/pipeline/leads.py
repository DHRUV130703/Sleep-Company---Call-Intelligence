"""Leads: group calls by phone number and keep each lead's roll-up fresh (PRD §7.4).

- find_or_create_lead(): at batch creation, one lead per normalised phone (else one per call).
- refresh_lead(): after a call is analysed — intent, status, owner, last call, "Path to conversion".
"""

import logging
from typing import Any

import phonenumbers
from pydantic import ValidationError
from sqlmodel import Session, col, select

from app.config import get_settings
from app.contracts import LeadPath, json_schema_for
from app.db import utcnow
from app.models import Analysis, Call, CallStatus, Lead, LeadStatus
from app.pipeline.grounding import resolve_when
from app.prompts import render
from app.providers import get_llm
from app.providers.base import ProviderError

log = logging.getLogger("leads")

DISPOSITION_TO_STATUS = {
    "converted": LeadStatus.won,
    "store_visit": LeadStatus.store_visit_planned,
    "callback_scheduled": LeadStatus.callback_scheduled,
    "agreed_next_step": LeadStatus.follow_up_pending,
    "follow_up_pending": LeadStatus.follow_up_pending,
    "no_outcome": LeadStatus.follow_up_pending,
    "not_interested": LeadStatus.lost,
    "not_qualified": LeadStatus.not_qualified,
}
NOT_CONNECTED_CODES = {"TOO_SHORT", "SILENT", "NOT_CONNECTED"}


def status_category(status: LeadStatus) -> str:
    if status == LeadStatus.won:
        return "won"
    if status in (LeadStatus.lost, LeadStatus.not_qualified):
        return "lost"
    return "in_progress"


def normalise_phone(raw: str) -> str | None:
    raw = (raw or "").strip().strip("'\"` ")  # exports often wrap numbers in quotes: '+91-98940…'
    if not raw:
        return None
    try:
        num = phonenumbers.parse(raw, get_settings().default_country)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(num):
        return None
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def display_phone(e164: str | None) -> str:
    """+919037125616 → "+91-90XXXXX616" when masking is on, "+91-9037125616" otherwise."""
    if not e164:
        return ""
    try:
        num = phonenumbers.parse(e164)
        cc, national = f"+{num.country_code}", str(num.national_number)
    except phonenumbers.NumberParseException:
        return e164
    if get_settings().mask_phones and len(national) > 5:
        national = national[:2] + "X" * (len(national) - 5) + national[-3:]
    return f"{cc}-{national}"


def find_or_create_lead(session: Session, *, phone: str, name: str, owner: str) -> Lead:
    e164 = normalise_phone(phone)
    lead = session.exec(select(Lead).where(Lead.phone_e164 == e164)).first() if e164 else None
    if lead is None:
        lead = Lead(phone_e164=e164, name=name.strip(), owner=owner.strip())
        session.add(lead)
        session.flush()
    elif name and not lead.name:
        lead.name = name.strip()
    return lead


def _latest_analyses(session: Session, lead_id: int) -> list[tuple[Call, Analysis]]:
    """Analysed calls of a lead, oldest first (one analysis per call — the newest)."""
    rows = session.exec(
        select(Call, Analysis)
        .join(Analysis, col(Analysis.call_id) == col(Call.id))
        .where(Call.lead_id == lead_id)
        .order_by(col(Analysis.id))
    ).all()
    latest: dict[int, tuple[Call, Analysis]] = {}
    for c, a in rows:
        assert c.id is not None
        latest[c.id] = (c, a)
    return sorted(latest.values(), key=lambda ca: ca[0].call_datetime or ca[0].created_at)


async def refresh_lead(session: Session, lead_id: int) -> None:
    lead = session.get(Lead, lead_id)
    if lead is None:
        return
    calls = session.exec(select(Call).where(Call.lead_id == lead_id)).all()
    analysed = _latest_analyses(session, lead_id)

    times = [c.call_datetime or c.created_at for c in calls]
    lead.last_call_at = max(times) if times else None

    if analysed:
        last_call, last = analysed[-1]
        r = last.result
        lead.intent_score = last.intent_score
        lead.intent_bucket = last.intent_bucket
        lead.owner = last_call.agent_name or lead.owner
        if not lead.name and r.get("customer", {}).get("name"):
            lead.name = r["customer"]["name"]
        if not lead.status_overridden:
            lead.status = DISPOSITION_TO_STATUS.get(last.disposition or "", LeadStatus.follow_up_pending)
        lead.path_summary = await _path_summary(analysed)
    elif any(c.status == CallStatus.skipped and c.error_code in NOT_CONNECTED_CODES for c in calls):
        lead.intent_score = None
        lead.intent_bucket = "not_available"

    lead.updated_at = utcnow()
    session.add(lead)
    session.commit()


async def _path_summary(analysed: list[tuple[Call, Analysis]]) -> dict[str, Any]:
    last_call, last = analysed[-1]
    single = {
        "bullets": last.result.get("summary", {}).get("bullets", []),
        "next_actions": last.result.get("next_actions", []),
        "based_on_calls": 1,
    }
    if len(analysed) == 1:
        return single

    s = get_settings()
    blocks = []
    for c, a in analysed:
        when = (c.call_datetime or c.created_at).strftime("%d %b %Y")
        r = a.result
        blocks.append(
            f"### Call on {when} ({'AI bot' if c.agent_type == 'ai' else 'human agent'})\n"
            + "\n".join(f"- {b}" for b in r.get("summary", {}).get("bullets", []))
            + f"\nOutcome: {r.get('outcome', {}).get('disposition')} — {r.get('outcome', {}).get('next_step')}"
            + f" (when: {r.get('outcome', {}).get('next_step_when') or 'not fixed'})"
        )
    prompt, _ = render("lead_path", calls="\n\n".join(blocks))
    try:
        data = await get_llm().json(
            prompt=prompt, schema=json_schema_for(LeadPath), model=s.lead_summary_model
        )
        path = LeadPath.model_validate(data).model_dump()
    except (ProviderError, ValidationError) as exc:
        log.warning("lead path summary failed; using latest call", extra={"reason": str(exc)[:200]})
        return single
    for a in path["next_actions"]:
        due = resolve_when(a["when"], last_call.call_datetime or last_call.created_at, s.default_timezone)
        a["due"] = due.isoformat() if due else None
    path["based_on_calls"] = len(analysed)
    return path
