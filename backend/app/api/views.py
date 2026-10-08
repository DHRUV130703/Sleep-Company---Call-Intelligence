"""Turn database rows into the JSON the frontend uses. Shared by several routers."""

from datetime import datetime
from typing import Any

from app.errors import MESSAGES, ErrorCode
from app.models import Analysis, Call, Lead
from app.pipeline.leads import display_phone, status_category


def error_message(call: Call) -> str | None:
    if not call.error_code:
        return None
    if call.error_detail:
        return call.error_detail
    try:
        return MESSAGES[ErrorCode(call.error_code)]
    except ValueError:
        return call.error_code


def call_row(call: Call, analysis: Analysis | None = None, lead: Lead | None = None) -> dict[str, Any]:
    r = analysis.result if analysis else {}
    return {
        "id": call.id,
        "batch_id": call.batch_id,
        "label": call.label,
        "agent_type": call.agent_type,
        "agent_name": call.agent_name,
        "campaign": call.campaign,
        "lead_id": call.lead_id,
        "lead_name": lead.name if lead else None,
        "call_datetime": iso(call.call_datetime or call.created_at),
        "duration_s": call.duration_s,
        "stage": call.stage,
        "status": call.status,
        "error_code": call.error_code,
        "error_message": error_message(call),
        "source_url": call.source_url,
        "outcome": (r.get("outcome") or {}).get("disposition"),
        "intent_score": analysis.intent_score if analysis else None,
        "intent_bucket": analysis.intent_bucket if analysis else None,
        "quality_pct": analysis.quality_pct if analysis else None,
        "language": r.get("language"),
        "one_liner": (r.get("summary") or {}).get("one_liner"),
    }


def lead_row(lead: Lead) -> dict[str, Any]:
    return {
        "id": lead.id,
        "name": lead.name or display_phone(lead.phone_e164) or f"Lead #{lead.id}",
        "has_name": bool(lead.name),
        "phone": display_phone(lead.phone_e164),
        "owner": lead.owner,
        "assignee": lead.assignee,
        "status": lead.status,
        "status_category": status_category(lead.status),
        "intent_score": lead.intent_score,
        "intent_bucket": lead.intent_bucket,
        "last_call_at": iso(lead.last_call_at),
    }


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None
