"""Chunked, resumable uploads (PRD §6.1.3). Chunks are stored in the database (app/storage.py).

    create_upload()  → Upload row
    write_chunk()    → stores chunk N as file "uploads/<id>/<N>" (verifies length and optional SHA-256)
    received()       → which chunks are stored (the client uses this to resume)
    complete()       → joins the chunks into "uploads/<id>/file.<ext>" and computes its SHA-256

Each chunk is its own stored file, so several chunks can be uploaded in parallel without overwriting
each other's progress.
"""

import hashlib
import math
from pathlib import Path

from sqlmodel import Session

from app import storage
from app.config import get_settings
from app.errors import AppError, ErrorCode
from app.models import Upload, UploadStatus

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB — a whole number of storage parts, so chunks join without copying


def chunk_key(upload_id: str, index: int) -> str:
    return f"uploads/{upload_id}/{index}"


def total_chunks(upload: Upload) -> int:
    return max(1, math.ceil(upload.size / upload.chunk_size))


def expected_length(upload: Upload, index: int) -> int:
    if index < total_chunks(upload) - 1:
        return upload.chunk_size
    return upload.size - upload.chunk_size * (total_chunks(upload) - 1)


def create_upload(session: Session, filename: str, size: int, mime: str) -> Upload:
    s = get_settings()
    limit = (s.max_zip_gb if filename.lower().endswith(".zip") else s.max_file_gb) * 1024**3
    if size <= 0:
        raise AppError(ErrorCode.VALIDATION_ERROR, "The file is empty.")
    if size > limit:
        raise AppError(ErrorCode.FILE_TOO_LARGE, detail={"limit_gb": limit / 1024**3})
    upload = Upload(filename=Path(filename).name, size=size, mime=mime, chunk_size=CHUNK_SIZE)
    session.add(upload)
    session.commit()
    session.refresh(upload)
    return upload


def get_upload(session: Session, upload_id: str) -> Upload:
    upload = session.get(Upload, upload_id)
    if upload is None:
        raise AppError(ErrorCode.NOT_FOUND, "Upload not found. Start the upload again.")
    return upload


def received(upload: Upload) -> list[int]:
    sizes = storage.sizes(f"uploads/{upload.id}/")
    return [
        i
        for i in range(total_chunks(upload))
        if sizes.get(chunk_key(upload.id, i)) == expected_length(upload, i)
    ]


def write_chunk(upload: Upload, index: int, data: bytes, sha256: str | None) -> None:
    if upload.status == UploadStatus.complete:
        return  # already assembled; a late retry is harmless
    if not 0 <= index < total_chunks(upload):
        raise AppError(ErrorCode.VALIDATION_ERROR, f"Chunk {index} is out of range.")
    if len(data) != expected_length(upload, index):
        raise AppError(ErrorCode.UPLOAD_CORRUPT, f"Chunk {index} has the wrong size.")
    if sha256 and hashlib.sha256(data).hexdigest() != sha256.lower():
        raise AppError(ErrorCode.UPLOAD_CORRUPT, f"Chunk {index} was damaged in transit.")
    storage.put_bytes(chunk_key(upload.id, index), data)  # only visible once fully written


def complete(session: Session, upload: Upload) -> Upload:
    if upload.status == UploadStatus.complete:
        return upload
    have = received(upload)
    missing = [i for i in range(total_chunks(upload)) if i not in have]
    if missing:
        raise AppError(ErrorCode.UPLOAD_INCOMPLETE, detail={"missing_chunks": missing[:50]})

    final = f"uploads/{upload.id}/file{Path(upload.filename).suffix.lower()}"
    size = storage.concat(
        [chunk_key(upload.id, i) for i in range(total_chunks(upload))],
        final,
        upload.mime or "application/octet-stream",
    )
    if size != upload.size:
        storage.delete_file(final)
        raise AppError(ErrorCode.UPLOAD_CORRUPT)

    upload.sha256 = storage.sha256(final)
    upload.file_path = final
    upload.status = UploadStatus.complete
    session.add(upload)
    session.commit()
    session.refresh(upload)
    return upload


def delete_upload_files(upload_id: str) -> None:
    storage.delete_prefix(f"uploads/{upload_id}/")
