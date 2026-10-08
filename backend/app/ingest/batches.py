"""Create a batch: turn uploaded files / ZIPs / spreadsheet rows / links into calls + leads + first jobs."""

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import Session

from app.config import get_settings
from app.errors import AppError, ErrorCode
from app.ingest import sheet_reader, zip_reader
from app.ingest.chunks import get_upload
from app.ingest.sheet_reader import CallSpec
from app.models import (
    AgentType,
    AgentTypeMode,
    Batch,
    Call,
    CallStage,
    CallStatus,
    Job,
    JobEvent,
    SourceType,
    TranscriptScript,
    UploadStatus,
)
from app.pipeline.leads import find_or_create_lead


@dataclass
class BatchInput:
    name: str
    campaign: str
    agent_type_mode: AgentTypeMode
    transcript_script: TranscriptScript
    files: list[dict[str, Any]] = field(default_factory=list)  # {upload_id, agent_type?}
    sheet: dict[str, Any] | None = None  # {sheet_id, mapping}
    links: list[dict[str, Any]] = field(default_factory=list)  # {url, label?, agent_type?}


def sheet_path(sheet_id: str) -> Path:
    folder = get_settings().data_dir / "sheets"
    matches = list(folder.glob(f"{sheet_id}.*"))
    if not matches:
        raise AppError(ErrorCode.NOT_FOUND, "Spreadsheet not found. Upload it again.")
    return matches[0]


def _parse_dt(raw: str) -> datetime | None:
    raw = raw.strip()
    if not raw:
        return None
    tz = ZoneInfo(get_settings().default_timezone)
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %b %Y %H:%M",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=tz)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=tz)
    except ValueError:
        return None


def _agent(value: str | None, mode: AgentTypeMode) -> str | None:
    """ "ai" / "human" for this file or link; None if it must come from elsewhere (e.g. a ZIP manifest)."""
    if mode in (AgentTypeMode.ai, AgentTypeMode.human):
        return mode.value
    return sheet_reader.normalise_agent_type(value or "")


def _require_agent(value: str | None, mode: AgentTypeMode, what: str) -> str:
    agent = _agent(value, mode)
    if not agent:
        raise AppError(ErrorCode.VALIDATION_ERROR, f"{what} needs an agent type (AI or Human).")
    return agent


def collect_specs(
    session: Session, inp: BatchInput
) -> tuple[list[CallSpec], list[dict[str, str]], SourceType]:
    s = get_settings()
    raw_dir = s.data_dir / "audio" / "raw"
    specs: list[CallSpec] = []
    skipped: list[dict[str, str]] = []
    kinds: set[SourceType] = set()

    for f in inp.files:
        upload = get_upload(session, f["upload_id"])
        if upload.status != UploadStatus.complete or not upload.file_path:
            raise AppError(ErrorCode.UPLOAD_INCOMPLETE, f"'{upload.filename}' hasn't finished uploading.")
        agent = _agent(f.get("agent_type"), inp.agent_type_mode)  # may be None for a ZIP with a manifest
        path = Path(upload.file_path)
        if path.suffix.lower() == ".zip":
            kinds.add(SourceType.zip)
            result = zip_reader.extract_audio(path, raw_dir, s.max_calls_per_batch)
            skipped += [
                {"name": f"{upload.filename} › {x['name']}", "reason": x["reason"]} for x in result.skipped
            ]
            for e in result.entries:
                m = e.meta
                entry_agent = sheet_reader.normalise_agent_type(m.get("agent_type", "")) or agent
                if not entry_agent:
                    skipped.append(
                        {
                            "name": f"{upload.filename} › {e.name}",
                            "reason": "No agent type: add it to manifest.csv or choose AI / Human",
                        }
                    )
                    e.path.unlink(missing_ok=True)
                    continue
                specs.append(
                    CallSpec(
                        label=m.get("external_id") or m.get("lead_name") or Path(e.name).stem,
                        agent_type=entry_agent,
                        file_path=str(e.path),
                        upload_id=upload.id,
                        lead_name=m.get("lead_name", ""),
                        lead_phone=m.get("lead_phone", ""),
                        call_datetime=m.get("call_datetime", ""),
                        agent_name=m.get("agent_name", ""),
                        campaign=m.get("campaign", ""),
                        external_id=m.get("external_id", ""),
                    )
                )
            path.unlink(missing_ok=True)  # the ZIP itself is no longer needed
        elif path.suffix.lower() in zip_reader.AUDIO_EXTS:
            kinds.add(SourceType.files)
            raw_dir.mkdir(parents=True, exist_ok=True)
            dest = raw_dir / f"{upload.sha256}{path.suffix.lower()}"
            if not dest.exists():
                shutil.move(str(path), dest)
            specs.append(
                CallSpec(
                    label=Path(upload.filename).stem,
                    agent_type=_require_agent(
                        f.get("agent_type"), inp.agent_type_mode, f"'{upload.filename}'"
                    ),
                    file_path=str(dest),
                    upload_id=upload.id,
                )
            )
        else:
            skipped.append({"name": upload.filename, "reason": "Not an audio, video or ZIP file"})

    if inp.sheet:
        kinds.add(SourceType.sheet)
        headers, rows = sheet_reader.read_table(sheet_path(inp.sheet["sheet_id"]))
        check = sheet_reader.rows_to_specs(rows, inp.sheet["mapping"], inp.agent_type_mode.value)
        specs += check.specs
        skipped += [{"name": f"Row {p['row']}", "reason": p["message"]} for p in check.problems]

    seen_links: set[str] = set()
    for link in inp.links:
        url = (link.get("url") or "").strip()
        if not url or url.lower() in seen_links:
            continue
        seen_links.add(url.lower())
        kinds.add(SourceType.links)
        label = (link.get("label") or "").strip() or Path(url.split("?")[0]).stem or url[:60]
        specs.append(
            CallSpec(
                label=label[:120],
                agent_type=_require_agent(link.get("agent_type"), inp.agent_type_mode, "Each link"),
                source_url=url,
            )
        )

    source = kinds.pop() if len(kinds) == 1 else SourceType.files
    return specs, skipped, source


def create_batch(session: Session, inp: BatchInput) -> Batch:
    s = get_settings()
    specs, skipped, source = collect_specs(session, inp)
    if not specs:
        raise AppError(ErrorCode.NOTHING_TO_PROCESS, detail={"skipped": skipped[:50]})
    if len(specs) > s.max_calls_per_batch:
        raise AppError(ErrorCode.TOO_MANY_CALLS, detail={"limit": s.max_calls_per_batch, "found": len(specs)})

    batch = Batch(
        name=inp.name.strip() or f"Batch {datetime.now(ZoneInfo(s.default_timezone)):%d %b %H:%M}",
        campaign=inp.campaign.strip(),
        source_type=source,
        agent_type_mode=inp.agent_type_mode,
        transcript_script=inp.transcript_script,
        stats={"skipped_inputs": skipped[:200], "calls": len(specs)},
    )
    session.add(batch)
    session.flush()
    assert batch.id is not None

    for spec in specs:
        # Calls with the same phone number share a lead; calls without one get their own lead.
        lead = find_or_create_lead(session, phone=spec.lead_phone, name=spec.lead_name, owner=spec.agent_name)
        call = Call(
            batch_id=batch.id,
            label=spec.label,
            agent_type=AgentType(spec.agent_type),
            agent_name=spec.agent_name,
            campaign=spec.campaign or inp.campaign.strip(),
            lead_id=lead.id,
            external_id=spec.external_id,
            source_url=spec.source_url,
            upload_id=spec.upload_id,
            raw_path=spec.file_path,
            call_datetime=_parse_dt(spec.call_datetime),
        )
        session.add(call)
        session.flush()
        assert call.id is not None
        first = CallStage.preparing if spec.file_path else CallStage.downloading
        call.stage = first
        session.add(Job(call_id=call.id, stage=first))
        session.add(
            JobEvent(
                batch_id=batch.id, call_id=call.id, stage=first, status=CallStatus.queued, message="Waiting"
            )
        )
    session.commit()
    session.refresh(batch)
    return batch
