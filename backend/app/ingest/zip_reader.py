"""Safe ZIP extraction (PRD §6.1.3).

- Only audio/video entries are extracted; everything else is listed as skipped with a reason.
- Entries are written to OUR file names (a random id), so a malicious path like ../../etc can't escape.
- Zip-bomb guard: total uncompressed size and entry count are capped before anything is extracted.
- An optional manifest.csv / manifest.xlsx inside the ZIP adds metadata (same columns as the spreadsheet
  flow, with the file name in the recording column).
"""

import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from uuid import uuid4

from app.errors import AppError, ErrorCode
from app.ingest import sheet_reader

AUDIO_EXTS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".mp4",
    ".aac",
    ".ogg",
    ".opus",
    ".webm",
    ".flac",
    ".amr",
    ".mpeg",
    ".mpga",
    ".3gp",
    ".wma",
    ".mov",
}
MAX_RATIO = 10  # uncompressed may be at most 10× the ZIP size …
MAX_TOTAL_BYTES = 20 * 1024**3  # … and at most 20 GB


@dataclass
class ZipEntry:
    name: str  # original name inside the ZIP
    path: Path  # where we extracted it
    meta: dict[str, str] = field(default_factory=dict)


@dataclass
class ZipResult:
    entries: list[ZipEntry] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)  # {name, reason}


def _ignored(name: str) -> bool:
    p = PurePosixPath(name)
    hidden = any(part.startswith(".") and part not in (".", "..") for part in p.parts)
    return name.endswith("/") or "__MACOSX" in p.parts or hidden


def _unsafe(name: str) -> bool:
    p = PurePosixPath(name.replace("\\", "/"))
    return p.is_absolute() or ".." in p.parts or (len(name) > 1 and name[1] == ":")


def extract_audio(zip_path: Path, dest_dir: Path, max_entries: int) -> ZipResult:
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise AppError(ErrorCode.BAD_ARCHIVE, detail={"reason": str(exc)[:200]}) from exc

    with zf:
        infos = [i for i in zf.infolist() if not _ignored(i.filename)]
        total = sum(i.file_size for i in infos)
        if total > min(MAX_TOTAL_BYTES, MAX_RATIO * max(zip_path.stat().st_size, 1)):
            raise AppError(ErrorCode.BAD_ARCHIVE, "This ZIP expands to an unsafe size.")
        if len(infos) > max_entries * 2 + 10:
            raise AppError(ErrorCode.BAD_ARCHIVE, "This ZIP has too many files.")

        result = ZipResult()
        manifest = _read_manifest(zf, infos, dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for info in infos:
            name = info.filename
            base = PurePosixPath(name).name
            if base.lower().startswith("manifest."):
                continue
            if _unsafe(name):
                result.skipped.append({"name": name, "reason": "Unsafe path inside the ZIP"})
                continue
            ext = PurePosixPath(base).suffix.lower()
            if ext not in AUDIO_EXTS:
                result.skipped.append({"name": name, "reason": "Not an audio or video file"})
                continue
            if info.flag_bits & 0x1:
                result.skipped.append({"name": name, "reason": "Password-protected"})
                continue
            out = dest_dir / f"{uuid4().hex}{ext}"
            with zf.open(info) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            result.entries.append(ZipEntry(name=name, path=out, meta=manifest.get(base.lower(), {})))
        return result


def _read_manifest(
    zf: zipfile.ZipFile, infos: list[zipfile.ZipInfo], tmp_dir: Path
) -> dict[str, dict[str, str]]:
    """{file name (lower case) → metadata row} from manifest.csv/.xlsx, if present."""
    info = next(
        (i for i in infos if PurePosixPath(i.filename).name.lower() in ("manifest.csv", "manifest.xlsx")),
        None,
    )
    if info is None:
        return {}
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = tmp_dir / f"manifest-{uuid4().hex}{PurePosixPath(info.filename).suffix.lower()}"
    try:
        with zf.open(info) as src, tmp.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        headers, rows = sheet_reader.read_table(tmp)
        mapping = sheet_reader.suggest_mapping(headers)
        file_col = mapping.get("recording_url")
        if not file_col:
            return {}
        out = {}
        for row in rows:
            fname = PurePosixPath(row.get(file_col, "").replace("\\", "/")).name.lower()
            if fname:
                out[fname] = {
                    fld: row.get(col, "") for fld, col in mapping.items() if col and fld != "recording_url"
                }
        return out
    except AppError:
        return {}
    finally:
        tmp.unlink(missing_ok=True)
