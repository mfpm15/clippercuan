"""Transkripsi dengan timestamp per kata (faster-whisper, berjalan lokal di CPU/GPU)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .config import MODELS_DIR

_MODEL_CACHE: dict = {}


def _load(model_name: str):
    if model_name not in _MODEL_CACHE:
        from faster_whisper import WhisperModel

        device, compute = "cpu", "int8"
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                device, compute = "cuda", "float16"
        except Exception:
            pass
        _MODEL_CACHE[model_name] = WhisperModel(model_name, device=device, compute_type=compute, download_root=str(MODELS_DIR))
    return _MODEL_CACHE[model_name]


def transcribe(
    wav: Path,
    model_name: str = "small",
    language: str = "auto",
    translate_en: bool = False,
    progress: Callable[[float, str], None] = lambda p, m: None,
    duration: float | None = None,
) -> dict:
    """Hasil: {"language": "id", "words": [{"w","s","e"}], "segments": [{"text","s","e","words":[idx..]}]}"""
    progress(0.0, f"Memuat model Whisper '{model_name}' (unduh sekali di awal)…")
    model = _load(model_name)
    # Kirim sampel mentah (WAV 16 kHz mono dari ffmpeg) agar tidak bergantung pada versi PyAV.
    import wave

    import numpy as np

    with wave.open(str(wav), "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    segs, info = model.transcribe(
        audio,
        language=None if language in ("", "auto", None) else language,
        task="translate" if translate_en else "transcribe",
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=False,
    )
    total = duration or info.duration or 1
    words, segments = [], []
    for seg in segs:
        idx = []
        for w in seg.words or []:
            text = w.word.strip()
            if not text:
                continue
            idx.append(len(words))
            words.append({"w": text, "s": round(w.start, 3), "e": round(max(w.end, w.start + 0.05), 3), "p": round(w.probability, 3)})
        if idx:
            segments.append({"text": seg.text.strip(), "s": words[idx[0]]["s"], "e": words[idx[-1]]["e"], "words": idx})
        progress(min(seg.end / total, 1.0), f"Transkripsi {int(seg.end)}/{int(total)} detik")
    return {"language": info.language, "words": words, "segments": segments}


def load_or_transcribe(cache: Path, wav: Path, **kw) -> dict:
    key = {k: kw.get(k) for k in ("model_name", "language", "translate_en")}
    if cache.exists():
        data = json.loads(cache.read_text("utf-8"))
        if data.get("_key") == key:
            return data
    data = transcribe(wav, **kw)
    data["_key"] = key
    cache.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
    return data
