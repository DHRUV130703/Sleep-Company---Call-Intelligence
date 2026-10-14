"""ffmpeg wrappers. All audio work goes through these four functions.

ffmpeg comes from the computer (`brew install ffmpeg`) or, where there is none (Vercel), from the
`imageio-ffmpeg` package, which ships a ready-made ffmpeg. Only ffmpeg is needed (no ffprobe).
"""

import asyncio
import re
import shutil
from dataclasses import dataclass
from functools import lru_cache
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


@lru_cache
def ffmpeg_path() -> str:
    """The installed ffmpeg if there is one, otherwise the copy bundled with imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # a pip package with an ffmpeg binary inside (used on Vercel)

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except (ImportError, RuntimeError) as exc:
        raise AudioError("ffmpeg is not installed (macOS: brew install ffmpeg)") from exc


async def _run(*args: str, timeout: float = 600) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_path(), *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        raise AudioError("ffmpeg timed out") from None
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


def _clock_to_seconds(h: str, m: str, s: str) -> float:
    return int(h) * 3600 + int(m) * 60 + float(s)


def _channels(stream_line: str) -> int:
    """'Audio: mp3, 44100 Hz, stereo, fltp' → 2. ffmpeg names the layout rather than counting it."""
    low = stream_line.lower()
    if m := re.search(r"(\d+) channels", low):
        return int(m.group(1))
    for name, n in (("mono", 1), ("stereo", 2), ("2.1", 3), ("quad", 4), ("5.1", 6), ("7.1", 8)):
        if re.search(rf"(?<![\w.]){re.escape(name)}\b", low):
            return n
    return 1


async def probe(path: Path) -> Probe:
    """Duration, channel count and whether there is any audio, read from `ffmpeg -i`'s report."""
    _, _, err = await _run("-hide_banner", "-i", str(path), timeout=60)
    if "Invalid data found" in err or "No such file" in err or "Duration:" not in err:
        raise AudioError(err.strip().splitlines()[-1][:300] if err.strip() else "not an audio file")
    audio_lines = [ln for ln in err.splitlines() if "Stream #" in ln and "Audio:" in ln]
    duration = 0.0
    if m := re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err):
        duration = _clock_to_seconds(*m.groups())
    if audio_lines and duration <= 0:
        # Some recordings (streamed .webm/.mp4) don't state their length: decode them to measure it.
        _, _, decoded = await _run("-hide_banner", "-i", str(path), "-vn", "-f", "null", "-")
        times = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", decoded)
        duration = _clock_to_seconds(*times[-1]) if times else 0.0
    return Probe(duration_s=duration, channels=_channels(audio_lines[0]) if audio_lines else 0,
                 has_audio=bool(audio_lines))  # fmt: skip


async def normalise(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp.mp3")
    code, _, err = await _run("-y", "-loglevel", "error", "-i", str(src), *NORM_ARGS, str(tmp))
    if code != 0:
        tmp.unlink(missing_ok=True)
        raise AudioError(err.strip()[:300] or "ffmpeg failed")
    tmp.replace(dst)  # atomic: a half-written file is never left at dst


async def max_volume_db(path: Path) -> float:
    """Loudest point in dB (0 = max). Below about -50 dB the recording is effectively silent."""
    _, _, err = await _run("-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-")
    m = re.search(r"max_volume:\s*(-?[\d.]+|-inf) dB", err)
    if not m or m.group(1) == "-inf":
        return -100.0
    return float(m.group(1))


async def cut(src: Path, dst: Path, start_s: float, length_s: float) -> None:
    code, _, err = await _run(
        "-y", "-loglevel", "error", "-ss", f"{start_s:.2f}", "-t", f"{length_s:.2f}", "-i", str(src),
        *NORM_ARGS, str(dst),
    )  # fmt: skip
    if code != 0:
        raise AudioError(err.strip()[:300] or "ffmpeg cut failed")
