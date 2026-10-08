"""Chunked, resumable uploads (PRD §6.1.3).

    create_upload()  → Upload row + empty folder data/uploads/<id>/
    write_chunk()    → saves chunk N as <N>.part (verifies length and optional SHA-256)
    received()       → which chunks are on disk (the client uses this to resume)
    complete()       → joins the parts into one file, computes its SHA-256, deletes the parts

Received chunks are read from disk rather than stored in the database, so several chunks can be
uploaded in parallel without overwriting each other's progress.
"""

import hashlib
import math
import shutil
from pathlib import Path

from sqlmodel import Session

from app.config import get_settings
from app.errors import AppError, ErrorCode
from app.models import Upload, UploadStatus

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB


def upload_dir(upload_id: str) -> Path:
    return get_settings().data_dir / "uploads" / upload_id


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
    upload_dir(upload.id).mkdir(parents=True, exist_ok=True)
    return upload


def get_upload(session: Session, upload_id: str) -> Upload:
    upload = session.get(Upload, upload_id)
    if upload is None:
        raise AppError(ErrorCode.NOT_FOUND, "Upload not found. Start the upload again.")
    return upload


def received(upload: Upload) -> list[int]:
    folder = upload_dir(upload.id)
    done = []
    for i in range(total_chunks(upload)):
        part = folder / f"{i}.part"
        if part.exists() and part.stat().st_size == expected_length(upload, i):
            done.append(i)
    return done


def write_chunk(upload: Upload, index: int, data: bytes, sha256: str | None) -> None:
    if upload.status == UploadStatus.complete:
        return  # already assembled; a late retry is harmless
    if not 0 <= index < total_chunks(upload):
        raise AppError(ErrorCode.VALIDATION_ERROR, f"Chunk {index} is out of range.")
    if len(data) != expected_length(upload, index):
        raise AppError(ErrorCode.UPLOAD_CORRUPT, f"Chunk {index} has the wrong size.")
    if sha256 and hashlib.sha256(data).hexdigest() != sha256.lower():
        raise AppError(ErrorCode.UPLOAD_CORRUPT, f"Chunk {index} was damaged in transit.")
    folder = upload_dir(upload.id)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f"{index}.part.tmp"
    tmp.write_bytes(data)
    tmp.replace(folder / f"{index}.part")  # atomic: a half-written chunk never looks complete


def complete(session: Session, upload: Upload) -> Upload:
    if upload.status == UploadStatus.complete:
        return upload
    have = received(upload)
    missing = [i for i in range(total_chunks(upload)) if i not in have]
    if missing:
        raise AppError(ErrorCode.UPLOAD_INCOMPLETE, detail={"missing_chunks": missing[:50]})

    folder = upload_dir(upload.id)
    final = folder / f"file{Path(upload.filename).suffix.lower()}"
    digest = hashlib.sha256()
    with final.open("wb") as out:
        for i in range(total_chunks(upload)):
            part = folder / f"{i}.part"
            with part.open("rb") as f:
                while block := f.read(1024 * 1024):
                    digest.update(block)
                    out.write(block)
    if final.stat().st_size != upload.size:
        final.unlink(missing_ok=True)
        raise AppError(ErrorCode.UPLOAD_CORRUPT)
    for i in range(total_chunks(upload)):
        (folder / f"{i}.part").unlink(missing_ok=True)

    upload.sha256 = digest.hexdigest()
    upload.file_path = str(final)
    upload.status = UploadStatus.complete
    session.add(upload)
    session.commit()
    session.refresh(upload)
    return upload


def delete_upload_files(upload_id: str) -> None:
    shutil.rmtree(upload_dir(upload_id), ignore_errors=True)
