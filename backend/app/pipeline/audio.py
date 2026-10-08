"""ffprobe / ffmpeg wrappers. All audio work goes through these four functions."""

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path

# Normalised format: mono, 16 kHz, 32 kbps MP3. Small (≈14 MB per hour, under OpenAI's 25 MB limit
# for a 10-minute chunk many times over), plays in every browser, and is plenty for speech.
NORM_ARGS = ["-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "32k"]


class AudioError(Exception):
    pass


@dataclass
class Probe:
    duration_s: float
    channels: int
    has_audio: bool


async def _run(*args: str, timeout: float = 600) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        raise AudioError(f"{args[0]} timed out") from None
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


async def probe(path: Path) -> Probe:
    code, out, err = await _run(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,channels",
        "-of",
        "json",
        str(path),
        timeout=60,
    )
    if code != 0:
        raise AudioError(err.strip()[:300] or "ffprobe failed")
    data = json.loads(out or "{}")
    audio_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    duration = float(data.get("format", {}).get("duration") or 0)
    channels = int(audio_streams[0].get("channels", 1)) if audio_streams else 0
    return Probe(duration_s=duration, channels=channels, has_audio=bool(audio_streams))


async def normalise(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp.mp3")
    code, _, err = await _run("ffmpeg", "-y", "-loglevel", "error", "-i", str(src), *NORM_ARGS, str(tmp))
    if code != 0:
        tmp.unlink(missing_ok=True)
        raise AudioError(err.strip()[:300] or "ffmpeg failed")
    tmp.replace(dst)  # atomic: a half-written file is never left at dst


async def max_volume_db(path: Path) -> float:
    """Loudest point in dB (0 = max). Below about -50 dB the recording is effectively silent."""
    _, _, err = await _run(
        "ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"
    )
    m = re.search(r"max_volume:\s*(-?[\d.]+|-inf) dB", err)
    if not m or m.group(1) == "-inf":
        return -100.0
    return float(m.group(1))


async def cut(src: Path, dst: Path, start_s: float, length_s: float) -> None:
    code, _, err = await _run(
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-ss",
        f"{start_s:.2f}",
        "-t",
        f"{length_s:.2f}",
        "-i",
        str(src),
        *NORM_ARGS,
        str(dst),
    )
    if code != 0:
        raise AudioError(err.strip()[:300] or "ffmpeg cut failed")
