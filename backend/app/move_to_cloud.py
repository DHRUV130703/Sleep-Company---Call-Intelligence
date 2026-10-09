"""One-time move of a local install to the cloud database: `make move-to-cloud`.

Copies every row from the local SQLite file (data/app.db) into the database in DATABASE_URL, then
stores the recordings, uploads, spreadsheets and raw transcripts from data/ in that database too
(app/storage.py). File paths in the copied rows become storage keys.

The local data/ folder is left untouched as a backup; delete it yourself once the app works.
Refuses to run if the cloud database already has batches (so nothing is copied twice).
"""

import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, select, text
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registers every table)
from app import storage
from app.config import get_settings
from app.db import get_engine

SKIP_TABLES = {"blobs", "blob_parts", "worker_heartbeats"}  # new tables, empty locally


def _key(path: str | None, prefix: str) -> str | None:
    return f"{prefix}/{Path(path).name}" if path else None


def copy_rows(src_url: str) -> list[tuple[str, Path]]:
    """Copy all tables. Returns the files to upload as (storage key, local path)."""
    src, dst = create_engine(src_url), get_engine()
    files: list[tuple[str, Path]] = []
    for table in SQLModel.metadata.sorted_tables:  # parents before children (foreign keys)
        if table.name in SKIP_TABLES:
            continue
        with src.connect() as c:
            rows: list[dict[str, Any]] = [dict(r._mapping) for r in c.execute(select(table))]
        for r in rows:
            if table.name == "calls":
                for col, prefix in (("raw_path", "audio/raw"), ("audio_path", "audio/norm")):
                    if (key := _key(r[col], prefix)) and r[col]:
                        files.append((key, Path(r[col])))
                    r[col] = key
            if table.name == "uploads" and r["file_path"]:
                key = _key(r["file_path"], f"uploads/{r['id']}")
                files.append((key, Path(r["file_path"])))  # type: ignore[arg-type]
                r["file_path"] = key
        with dst.begin() as c:
            for i in range(0, len(rows), 200):
                c.execute(table.insert(), rows[i : i + 200])
            if "id" in table.c and rows and isinstance(rows[0]["id"], int):
                # Continue numbering after the copied ids.
                c.execute(text(f"SELECT setval('{table.name}_id_seq', (SELECT max(id) FROM {table.name}))"))
        print(f"  {table.name}: {len(rows)} rows")
    return files


def upload_files(files: list[tuple[str, Path]], data_dir: Path) -> None:
    for folder in ("sheets", "transcripts_raw"):
        if (data_dir / folder).is_dir():
            files += [(f"{folder}/{p.name}", p) for p in sorted((data_dir / folder).iterdir()) if p.is_file()]
    done = missing = 0
    for key, path in dict(files).items():
        if not path.is_file():
            missing += 1
            continue
        if not storage.exists(key):
            storage.put_file(
                key, path, "audio/mpeg" if key.startswith("audio/norm/") else "application/octet-stream"
            )
        done += 1
        print(f"\r  files: {done} stored", end="", flush=True)
    print(f"\n  files missing on disk (already deleted earlier): {missing}")


def main() -> None:
    s = get_settings()
    if not s.database_url:
        sys.exit("Set DATABASE_URL in .env to the cloud database first.")
    local_db = s.data_dir / "app.db"
    if not local_db.exists():
        sys.exit(f"No local database at {local_db} — nothing to move.")
    dst = get_engine()
    with dst.connect() as c:
        if c.execute(select(func.count()).select_from(SQLModel.metadata.tables["batches"])).scalar():
            sys.exit("The cloud database already has data. Nothing was copied.")

    print("Copying tables…")
    files = copy_rows(f"sqlite:///{local_db}")
    print("Storing recordings, uploads, spreadsheets and raw transcripts in the database…")
    upload_files(files, s.data_dir)
    n, size = storage.total_size()
    print(
        f"Done: {n} files ({size / 1e6:.0f} MB) in the cloud database. The data/ folder is kept as a backup."
    )


if __name__ == "__main__":
    main()
