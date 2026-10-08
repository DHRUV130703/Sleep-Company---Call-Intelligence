"""Download a recording from a link (PRD §6.1.3).

- Streams to disk (never holds the whole file in memory), with a size cap.
- Google Drive and Dropbox share links are converted to direct-download links.
- SSRF guard: links that resolve to private/local network addresses are refused
  (set ALLOW_PRIVATE_URLS=true only for local testing).
- Errors are raised as StageError with a user-friendly code (404 → LINK_NOT_FOUND, …).
"""

import asyncio
import hashlib
import ipaddress
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlparse, urlunparse
from uuid import uuid4

import httpx

from app.config import get_settings
from app.errors import ErrorCode
from app.ingest.zip_reader import AUDIO_EXTS
from app.pipeline.errors import StageError

CONTENT_TYPE_EXT = {
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/wave": ".wav",
    "audio/mp4": ".m4a", "audio/x-m4a": ".m4a", "audio/aac": ".aac", "audio/ogg": ".ogg", "audio/opus": ".opus",
    "audio/webm": ".webm", "audio/flac": ".flac", "audio/amr": ".amr", "video/mp4": ".mp4", "video/webm": ".webm",
    "video/quicktime": ".mov",
}  # fmt: skip


@dataclass
class Downloaded:
    path: Path
    sha256: str
    size: int
    filename: str  # name the server gave the file (Content-Disposition), "" if none


def _disposition_filename(header: str) -> str:
    m = re.search(r"filename\*=(?:UTF-8'')?([^;]+)|filename=\"?([^\";]+)\"?", header, re.I)
    if not m:
        return ""
    return Path(unquote((m.group(1) or m.group(2)).strip())).name


def direct_link(url: str) -> str:
    """Turn common share links into direct-download links."""
    p = urlparse(url)
    if p.netloc.endswith("drive.google.com"):
        m = re.search(r"/file/d/([\w-]+)", p.path)
        file_id = m.group(1) if m else parse_qs(p.query).get("id", [""])[0]
        if file_id:
            return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    if p.netloc.endswith("dropbox.com"):
        q = parse_qs(p.query)
        q["dl"] = ["1"]
        return urlunparse(p._replace(query=urlencode(q, doseq=True)))
    return url


async def _check_host(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise StageError(ErrorCode.LINK_INVALID)
    if get_settings().allow_private_urls:
        return
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, p.hostname, p.port or 443)
    except socket.gaierror as exc:
        raise StageError(ErrorCode.LINK_UNREACHABLE, detail=f"Unknown host {p.hostname}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise StageError(ErrorCode.LINK_BLOCKED)


def _extension(url: str, content_type: str, filename: str = "") -> str:
    for candidate in (filename, urlparse(url).path):
        ext = Path(candidate).suffix.lower()
        if ext in AUDIO_EXTS:
            return ext
    return CONTENT_TYPE_EXT.get(content_type.split(";")[0].strip().lower(), ".bin")


async def download(
    url: str, dest_dir: Path, *, transport: httpx.AsyncBaseTransport | None = None
) -> Downloaded:
    s = get_settings()
    max_bytes = int(s.max_file_gb * 1024**3)
    url = direct_link(url.strip())
    await _check_host(url)
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest_dir / f"{uuid4().hex}.part"
    digest = hashlib.sha256()
    size = 0
    timeout = httpx.Timeout(connect=30, read=600, write=60, pool=30)
    try:
        async with (
            httpx.AsyncClient(
                follow_redirects=True, max_redirects=5, timeout=timeout, transport=transport
            ) as client,
            client.stream("GET", url, headers={"User-Agent": "LimeZip/1.0"}) as res,
        ):
            if res.status_code == 404:
                raise StageError(ErrorCode.LINK_NOT_FOUND)
            if res.status_code in (401, 403):
                raise StageError(ErrorCode.LINK_FORBIDDEN)
            if res.status_code >= 500 or res.status_code == 429:
                raise StageError(ErrorCode.LINK_UNREACHABLE, detail=f"HTTP {res.status_code}", retryable=True)
            if res.status_code >= 400:
                raise StageError(ErrorCode.LINK_UNREACHABLE, detail=f"HTTP {res.status_code}")
            ctype = res.headers.get("content-type", "")
            if ctype.startswith("text/html"):
                raise StageError(
                    ErrorCode.NOT_AUDIO, detail="The link opens a web page, not a recording file."
                )
            if int(res.headers.get("content-length") or 0) > max_bytes:
                raise StageError(ErrorCode.FILE_TOO_LARGE)
            with tmp.open("wb") as f:
                async for block in res.aiter_bytes(1024 * 1024):
                    size += len(block)
                    if size > max_bytes:
                        raise StageError(ErrorCode.FILE_TOO_LARGE)
                    digest.update(block)
                    f.write(block)
            filename = _disposition_filename(res.headers.get("content-disposition", ""))
            ext = _extension(str(res.url), ctype, filename)
    except StageError:
        tmp.unlink(missing_ok=True)
        raise
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        raise StageError(ErrorCode.LINK_UNREACHABLE, detail=str(exc)[:200], retryable=True) from exc

    if size == 0:
        tmp.unlink(missing_ok=True)
        raise StageError(ErrorCode.NOT_AUDIO, detail="The link returned an empty file.")
    final = dest_dir / f"{digest.hexdigest()}{ext}"
    tmp.replace(final)
    return Downloaded(path=final, sha256=digest.hexdigest(), size=size, filename=filename)
