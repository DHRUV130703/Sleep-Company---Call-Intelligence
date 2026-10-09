"""Chunked uploads and spreadsheet preview (PRD §6.1)."""

from collections import Counter
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from app import storage
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.ingest import chunks, sheet_reader
from app.ingest.batches import read_sheet
from app.models import Upload
from app.pipeline.leads import normalise_phone

router = APIRouter(tags=["uploads"])

MAX_SHEET_BYTES = 20 * 1024 * 1024
PREVIEW_ROWS = 20


class UploadCreate(BaseModel):
    filename: str
    size: int
    mime: str = ""


def _status(upload: Upload) -> dict:
    return {
        "upload_id": upload.id,
        "filename": upload.filename,
        "size": upload.size,
        "chunk_size": upload.chunk_size,
        "total_chunks": chunks.total_chunks(upload),
        "received": chunks.received(upload),
        "status": upload.status,
        "sha256": upload.sha256,
    }


@router.post("/uploads")
def create_upload(body: UploadCreate, session: Session = Depends(get_session)) -> dict:
    return _status(chunks.create_upload(session, body.filename, body.size, body.mime))


@router.get("/uploads/{upload_id}")
def upload_status(upload_id: str, session: Session = Depends(get_session)) -> dict:
    return _status(chunks.get_upload(session, upload_id))


@router.put("/uploads/{upload_id}/chunks/{index}")
async def put_chunk(
    upload_id: str,
    index: int,
    request: Request,
    x_chunk_sha256: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    upload = chunks.get_upload(session, upload_id)
    data = await request.body()
    chunks.write_chunk(upload, index, data, x_chunk_sha256)
    return {"ok": True, "index": index}


@router.post("/uploads/{upload_id}/complete")
def complete_upload(upload_id: str, session: Session = Depends(get_session)) -> dict:
    return _status(chunks.complete(session, chunks.get_upload(session, upload_id)))


@router.delete("/uploads/{upload_id}")
def cancel_upload(upload_id: str, session: Session = Depends(get_session)) -> dict:
    upload = session.get(Upload, upload_id)
    if upload:
        chunks.delete_upload_files(upload.id)
        session.delete(upload)
        session.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Spreadsheets
# ---------------------------------------------------------------------------


class SheetCheckBody(BaseModel):
    mapping: dict[str, str | None]
    agent_type_mode: str = "column"


@router.post("/sheets/preview")
async def preview_sheet(file: UploadFile = File(...)) -> dict:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        raise AppError(ErrorCode.BAD_SHEET, "Use a .xlsx, .xls or .csv file.")
    data = await file.read(MAX_SHEET_BYTES + 1)
    if len(data) > MAX_SHEET_BYTES:
        raise AppError(ErrorCode.FILE_TOO_LARGE, "Spreadsheets can be up to 20 MB.")
    sheet_id = uuid4().hex
    storage.put_bytes(f"sheets/{sheet_id}{ext}", data)
    headers, rows = read_sheet(sheet_id)
    return {
        "sheet_id": sheet_id,
        "filename": file.filename,
        "headers": headers,
        "rows": rows[:PREVIEW_ROWS],
        "total_rows": len(rows),
        "mapping": sheet_reader.suggest_mapping(headers, rows),
        "fields": sheet_reader.FIELDS,
    }


@router.post("/sheets/{sheet_id}/check")
def check_sheet(sheet_id: str, body: SheetCheckBody) -> dict:
    _, rows = read_sheet(sheet_id)
    result = sheet_reader.rows_to_specs(rows, body.mapping, body.agent_type_mode)
    by_type = {"ai": 0, "human": 0}
    phones: Counter[str] = Counter()
    for spec in result.specs:
        by_type[spec.agent_type] += 1
        phones[normalise_phone(spec.lead_phone) or f"no-phone-{id(spec)}"] += 1
    return {
        "leads": len(phones),  # one lead per phone number; recordings of the same phone are stacked
        "stacked_phones": sum(1 for n in phones.values() if n > 1),
        "total_rows": result.total_rows,
        "valid": len(result.specs),
        "duplicates": result.duplicates,
        "problems": result.problems[:100],
        "problem_count": len(result.problems),
        "by_agent_type": by_type,
    }
