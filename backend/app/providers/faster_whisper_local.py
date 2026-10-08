"""Local speech-to-text with faster-whisper (Whisper on CTranslate2). No key, no network after the
one-time model download. This is the default transcriber.

Pipeline for one call:
    normalised mp3 (16 kHz mono, from ffmpeg)
      → Silero voice-activity detection: where is someone speaking?
      → utterances (short pauses merged, long stretches split at 20 s)
      → per utterance: pick English or Hindi (only these two), then transcribe with a domain hint
      → segments with speaker "?" — the LLM labels agent / customer afterwards

Why per utterance: Hinglish calls switch language every few seconds. Run over a whole call, Whisper
picks ONE language and translates or drops the other.
"""

import asyncio
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from app.contracts import RawSegment, RawTranscript
from app.providers.base import ProviderError

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")  # progress bars can hang inside the worker
log = logging.getLogger("providers")

SR = 16_000
MERGE_GAP_S = 0.35  # pauses shorter than this stay inside one utterance
MAX_CLIP_S = 20.0
TIMEOUT_S = 45 * 60
BEAM_SIZE = 1  # greedy: about twice as fast as beam search, nearly the same accuracy on short clips
CPU_THREADS = max(4, (os.cpu_count() or 4) - 2)  # leave a couple of cores for the app and Ollama
LANGS = ("en", "hi")

# English only when Whisper is clearly sure. Unclear phone audio of Hindi speech is otherwise often
# "heard" as English nonsense ("Hindi mein" → "Indeed, man"); Whisper's Hindi mode still writes
# English words in English, so Hindi is the safer default for a Hinglish call.
ENGLISH_MIN_PROB = 0.75
HALLUCINATIONS = {
    "",
    "thank you.",
    "thanks for watching!",
    "you",
    "bye.",
    ".",
    "subtitles by the amara.org community",
}

_lock = threading.Lock()  # one transcription at a time per process (shares the CPU and the loaded model)
_models: dict[str, Any] = {}


def load_model(name: str, compute_type: str) -> Any:
    """Load once per process. First use downloads the model (~1.6 GB for large-v3-turbo)."""
    from faster_whisper import WhisperModel

    if name not in _models:
        try:
            _models[name] = WhisperModel(
                name, device="cpu", compute_type=compute_type, cpu_threads=CPU_THREADS, local_files_only=True
            )
        except Exception:
            log.info("downloading the Whisper model (one time)", extra={"model": name})
            _models[name] = WhisperModel(
                name, device="cpu", compute_type=compute_type, cpu_threads=CPU_THREADS
            )
    return _models[name]


def load_audio(path: Path) -> Any:
    """16 kHz mono float32 samples, decoded by ffmpeg (same tool the rest of the pipeline uses)."""
    import numpy as np

    out = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(SR),
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(out, dtype=np.float32).copy()


def utterances(audio: Any) -> list[tuple[float, float]]:
    """(start_s, end_s) of each utterance, from Silero voice-activity detection."""
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    stamps = get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=300, speech_pad_ms=150))
    merged: list[list[float]] = []
    for st in stamps:
        start, end = st["start"] / SR, st["end"] / SR
        if merged and start - merged[-1][1] <= MERGE_GAP_S and end - merged[-1][0] <= MAX_CLIP_S:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    out: list[tuple[float, float]] = []
    for start, end in merged:
        n = max(1, int((end - start) // MAX_CLIP_S) + (1 if (end - start) % MAX_CLIP_S else 0))
        step = (end - start) / n
        out += [(start + k * step, start + (k + 1) * step) for k in range(n)]
    return out


class FasterWhisperTranscriber:
    name = "faster_whisper"

    def __init__(self, model: str, compute_type: str = "int8"):
        self.model = model
        self.compute_type = compute_type

    async def transcribe(self, audio: Path, *, script: str, context: str = "") -> RawTranscript:
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._run, audio), timeout=TIMEOUT_S)
        except TimeoutError:
            raise ProviderError("Local transcription took too long", retryable=True) from None

    def _run(self, path: Path) -> RawTranscript:
        with _lock:
            model = load_model(self.model, self.compute_type)
            audio = load_audio(path)
            segments: list[RawSegment] = []
            for start, end in utterances(audio):
                clip = audio[int(start * SR) : int(end * SR)]
                text = self._clip_text(model, clip)
                if text.lower() not in HALLUCINATIONS:
                    segments.append(
                        RawSegment(speaker="?", start=round(start, 2), end=round(end, 2), text=text)
                    )
        return RawTranscript(segments=segments)

    def _clip_text(self, model: Any, clip: Any) -> str:
        # One pass: Whisper detects the language while transcribing. Keep the result if it is Hindi, or
        # English it is sure about; otherwise (Urdu, Japanese, unsure English …) redo it as Hindi.
        text, info = self._transcribe(model, clip, None)
        probs = dict(info.all_language_probs or [])
        sure_english = info.language == "en" and probs.get("en", 0) >= ENGLISH_MIN_PROB
        if info.language != "hi" and not sure_english:
            text, _ = self._transcribe(model, clip, "hi")
        return text

    @staticmethod
    def _transcribe(model: Any, clip: Any, language: str | None) -> tuple[str, Any]:
        # No initial prompt: on unclear audio Whisper tends to "hear" the prompt text itself.
        parts, info = model.transcribe(
            clip,
            language=language,
            beam_size=BEAM_SIZE,
            condition_on_previous_text=False,
            without_timestamps=True,
        )
        return " ".join(p.text.strip() for p in parts).strip(), info


def preload(name: str, compute_type: str) -> None:
    with _lock:
        load_model(name, compute_type)
