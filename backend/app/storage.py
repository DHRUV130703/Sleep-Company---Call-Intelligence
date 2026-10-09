"""File storage in the database: recordings, uploads, spreadsheets and raw transcripts.

The app keeps nothing on the local disk. Every file is a row in `blobs` with its bytes in `blob_parts`
(1 MB each). Keys look like paths:

    audio/raw/<sha256>.<ext>          original recording (uploaded, from a ZIP, or downloaded)
    audio/norm/<sha256>.mp3           normalised recording (what the player streams)
    uploads/<upload_id>/<n>           chunk n of an upload in progress
    uploads/<upload_id>/file.<ext>    the finished upload
    sheets/<sheet_id>.<ext>           an uploaded spreadsheet
    transcripts_raw/<sha>-<name>.json speech-to-text output before speaker labelling

ffmpeg and the speech-to-text APIs need a real file: `local_copy(key)` writes a temporary copy and
removes it afterwards. Each function uses its own short database transaction.
"""

import hashlib
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, func, update
from sqlmodel import Session, col, select

from app.db import get_engine
from app.models_storage import Blob, BlobPart

PART_SIZE = 1024 * 1024
PARTS_PER_COMMIT = 8  # keeps each transaction to ~8 MB


def _write_parts(key: str, blocks: Iterator[bytes], content_type: str) -> int:
    """Store bytes as parts of exactly PART_SIZE (the last may be shorter) — range reads rely on this."""
    delete_file(key)
    idx = size = 0
    buf = b""
    with Session(get_engine()) as s:

        def flush(piece: bytes) -> None:
            nonlocal idx, size
            s.add(BlobPart(key=key, idx=idx, data=piece))
            idx, size = idx + 1, size + len(piece)
            if idx % PARTS_PER_COMMIT == 0:
                s.commit()

        for block in blocks:
            buf += block
            while len(buf) >= PART_SIZE:
                flush(buf[:PART_SIZE])
                buf = buf[PART_SIZE:]
        if buf or idx == 0:
            flush(buf)  # the last (short) part; an empty file still gets one empty part
        s.add(Blob(key=key, size=size, parts=idx, content_type=content_type))  # last: marks it complete
        s.commit()
    return size


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> int:
    return _write_parts(key, iter([data]), content_type)


def put_file(key: str, path: Path, content_type: str = "application/octet-stream") -> int:
    def blocks() -> Iterator[bytes]:
        with path.open("rb") as f:
            while block := f.read(PART_SIZE):
                yield block

    return _write_parts(key, blocks(), content_type)


def info(key: str | None) -> Blob | None:
    if not key:
        return None
    with Session(get_engine()) as s:
        return s.get(Blob, key)


def exists(key: str | None) -> bool:
    return info(key) is not None


def iter_parts(key: str, first: int = 0, last: int | None = None) -> Iterator[bytes]:
    """Yield the file's parts in order (optionally only parts first..last), a few at a time."""
    idx = first
    while last is None or idx <= last:
        with Session(get_engine()) as s:
            rows = s.exec(
                select(BlobPart.data)
                .where(BlobPart.key == key, col(BlobPart.idx) >= idx)
                .order_by(col(BlobPart.idx))
                .limit(PARTS_PER_COMMIT)
            ).all()
        if not rows:
            return
        for data in rows:
            if last is not None and idx > last:
                return
            yield data
            idx += 1


def read_bytes(key: str) -> bytes:
    if not exists(key):
        raise FileNotFoundError(key)
    return b"".join(iter_parts(key))


def iter_range(key: str, start: int, end: int) -> Iterator[bytes]:
    """Bytes start..end (inclusive) — for HTTP Range requests from the audio player."""
    first, last = start // PART_SIZE, end // PART_SIZE
    for n, data in enumerate(iter_parts(key, first, last), start=first):
        lo = start - n * PART_SIZE if n == first else 0
        hi = end - n * PART_SIZE + 1 if n == last else len(data)
        yield data[lo:hi]


def sha256(key: str) -> str:
    h = hashlib.sha256()
    for data in iter_parts(key):
        h.update(data)
    return h.hexdigest()


def delete_file(key: str) -> None:
    with Session(get_engine()) as s:
        s.execute(delete(Blob).where(col(Blob.key) == key))
        s.execute(delete(BlobPart).where(col(BlobPart.key) == key))
        s.commit()


def sizes(prefix: str) -> dict[str, int]:
    """{key: size} of every stored file whose key starts with `prefix` (one query)."""
    with Session(get_engine()) as s:
        rows = s.exec(select(Blob.key, Blob.size).where(col(Blob.key).startswith(prefix))).all()
    return dict(rows)  # type: ignore[arg-type]


def keys(prefix: str, older_than: datetime | None = None) -> list[str]:
    with Session(get_engine()) as s:
        q = select(Blob.key).where(col(Blob.key).startswith(prefix))
        if older_than is not None:
            q = q.where(col(Blob.created_at) < older_than)
        return list(s.exec(q.order_by(col(Blob.key))).all())


def delete_prefix(prefix: str) -> int:
    found = keys(prefix)
    for key in found:
        delete_file(key)
    return len(found)


def rename(src: str, dst: str) -> None:
    """Give a file a new key without copying its bytes. An existing file at `dst` is replaced."""
    if src == dst:
        return
    delete_file(dst)
    with Session(get_engine()) as s:
        s.execute(update(BlobPart).where(col(BlobPart.key) == src).values(key=dst))
        s.execute(update(Blob).where(col(Blob.key) == src).values(key=dst))
        s.commit()


def concat(srcs: list[str], dst: str, content_type: str = "application/octet-stream") -> int:
    """Join files into one (upload chunks → the finished upload) and delete the pieces.
    When every piece but the last is a whole number of parts (the normal 8 MB chunks), the parts are
    just re-labelled in the database; otherwise the bytes are copied."""
    blobs = [info(src) for src in srcs]
    if any(b is None for b in blobs):
        raise FileNotFoundError(next(src for src, b in zip(srcs, blobs, strict=True) if b is None))
    aligned = all(b.size == b.parts * PART_SIZE for b in blobs[:-1] if b)
    if not aligned:
        size = _write_parts(dst, (data for src in srcs for data in iter_parts(src)), content_type)
        for src in srcs:
            delete_file(src)
        return size

    delete_file(dst)
    offset = size = 0
    with Session(get_engine()) as s:
        for src, blob in zip(srcs, blobs, strict=True):
            assert blob is not None
            s.execute(
                update(BlobPart)
                .where(col(BlobPart.key) == src)
                .values(key=dst, idx=col(BlobPart.idx) + offset)
            )
            s.execute(delete(Blob).where(col(Blob.key) == src))
            offset, size = offset + blob.parts, size + blob.size
            s.commit()
        s.add(Blob(key=dst, size=size, parts=offset, content_type=content_type))
        s.commit()
    return size


def total_size() -> tuple[int, int]:
    """(number of files, total bytes) — shown in Settings → Health."""
    with Session(get_engine()) as s:
        n, size = s.exec(select(func.count(), func.sum(Blob.size))).one()
    return int(n), int(size or 0)  # CockroachDB returns the sum as a decimal


@contextmanager
def local_copy(key: str) -> Iterator[Path]:
    """A temporary file with the stored bytes, for tools that need a path (ffmpeg, zipfile, APIs)."""
    if not exists(key):
        raise FileNotFoundError(key)
    with tempfile.TemporaryDirectory(prefix="limezip-") as tmp:
        path = Path(tmp) / Path(key).name
        with path.open("wb") as f:
            for data in iter_parts(key):
                f.write(data)
        yield path
