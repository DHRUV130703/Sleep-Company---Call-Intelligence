"""Optional local speech-to-text with Whisper on the Apple Silicon GPU (mlx-whisper) — about twice as fast
as faster-whisper on a Mac. Use with TRANSCRIBER=mlx_whisper. No API key, no network after
the one-time model download.

Why per-utterance: Hinglish calls switch language mid-call. Whisper run over the whole call picks ONE
language and then either translates the other language or skips it. So we first find the stretches of
speech (simple energy-based voice detection), then transcribe each stretch on its own and let Whisper
detect English or Hindi for that stretch.

Whisper doesn't know who is speaking — segments come back with speaker "?" and Claude assigns
agent / customer afterwards (pipeline/analysis.py: label_speakers).
"""

import asyncio
import logging
import os
import threading
from pathlib import Path

import numpy as np

from app.contracts import RawSegment, RawTranscript
from app.providers.base import ProviderError

# No progress bars: they start a multiprocessing helper that can hang inside the worker.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
log = logging.getLogger("providers")

SR = 16_000
FRAME = int(0.03 * SR)  # 30 ms frames
MERGE_GAP_S = 0.35  # pauses shorter than this stay inside one utterance
PAD_S = 0.15
MIN_SPEECH_S = 0.3
MAX_CLIP_S = 20.0
LANGS = ("en", "hi")
TIMEOUT_S = 30 * 60
HALLUCINATIONS = {"", "thank you.", "thanks for watching!", "you", "bye.", "."}

_lock = threading.Lock()  # one Whisper run at a time (shares the GPU and the loaded model)
_model_dirs: dict[str, str] = {}


def model_dir(repo: str) -> str:
    """Local folder of the Whisper model. Uses the downloaded copy without going online; downloads
    (~1.6 GB) only the very first time. Passing a folder to mlx-whisper means no network at all later."""
    if repo in _model_dirs:
        return _model_dirs[repo]
    if Path(repo).is_dir():
        path = repo
    else:
        from huggingface_hub import snapshot_download

        try:
            path = snapshot_download(repo, local_files_only=True)
        except Exception:
            log.info("downloading the Whisper model (one time, ~1.6 GB)", extra={"model": repo})
            path = snapshot_download(repo)
    _model_dirs[repo] = path
    return path


def preload(repo: str) -> None:
    """Load Whisper into memory once (called when the worker starts) so the first call isn't slow."""
    import mlx.core as mx
    from mlx_whisper.transcribe import ModelHolder

    with _lock:
        ModelHolder.get_model(model_dir(repo), mx.float16)


def speech_regions(samples: np.ndarray) -> list[tuple[float, float]]:
    """(start_s, end_s) of speech, from frame loudness relative to the background noise."""
    n = len(samples) // FRAME
    if n == 0:
        return []
    frames = samples[: n * FRAME].reshape(n, FRAME)
    db = 20 * np.log10(np.sqrt((frames**2).mean(axis=1)) + 1e-9)
    floor = np.percentile(db, 10)
    threshold = max(floor + 10, -50.0)
    voiced = db > threshold

    regions: list[list[float]] = []
    for i, v in enumerate(voiced):
        t = i * FRAME / SR
        if not v:
            continue
        if regions and t - regions[-1][1] <= MERGE_GAP_S:
            regions[-1][1] = t + FRAME / SR
        else:
            regions.append([t, t + FRAME / SR])

    out: list[tuple[float, float]] = []
    total = len(samples) / SR
    for start, end in regions:
        if end - start < MIN_SPEECH_S:
            continue
        start, end = max(0.0, start - PAD_S), min(total, end + PAD_S)
        pieces = int(np.ceil((end - start) / MAX_CLIP_S))  # very long stretches are split evenly
        step = (end - start) / pieces
        out += [(start + k * step, start + (k + 1) * step) for k in range(pieces)]
    return out


class LocalWhisperTranscriber:
    name = "mlx_whisper"

    def __init__(self, model: str):
        self.model = model

    async def transcribe(self, audio: Path, *, script: str, context: str = "") -> RawTranscript:
        try:
            # Generous limit (Whisper runs at roughly half of real time here): a stuck run becomes a
            # visible, retryable error instead of "Transcribing" forever.
            return await asyncio.wait_for(asyncio.to_thread(self._run, audio), timeout=TIMEOUT_S)
        except TimeoutError:
            raise ProviderError("Local transcription took too long", retryable=True) from None

    def _run(self, audio: Path) -> RawTranscript:
        import mlx_whisper  # imported lazily: heavy, and only needed when this provider is used
        from mlx_whisper.audio import load_audio

        samples = load_audio(str(audio))
        segments: list[RawSegment] = []
        with _lock:
            for start, end in speech_regions(samples):
                clip = samples[int(start * SR) : int(end * SR)]
                text = self._clip_text(mlx_whisper, clip)
                if text.lower() not in HALLUCINATIONS:
                    segments.append(
                        RawSegment(speaker="?", start=round(start, 2), end=round(end, 2), text=text)
                    )
        return RawTranscript(segments=segments)

    def _clip_text(self, mlx_whisper, clip: np.ndarray) -> str:  # type: ignore[no-untyped-def]
        opts = {
            "path_or_hf_repo": model_dir(self.model),
            "condition_on_previous_text": False,
            "verbose": None,
        }
        result = mlx_whisper.transcribe(clip, **opts)
        if result.get("language") not in LANGS:  # short clips sometimes come back as Urdu/Marathi/…
            result = mlx_whisper.transcribe(clip, language="hi", **opts)
        return str(result.get("text", "")).strip()
