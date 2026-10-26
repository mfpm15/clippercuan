"""Pembungkus ffmpeg: probe, ekstrak audio, ambil frame, energi audio."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import FFMPEG

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class FFmpegError(RuntimeError):
    pass


def run(args: list[str], cwd: str | Path | None = None, capture: bool = True) -> subprocess.CompletedProcess:
    cmd = [FFMPEG, "-hide_banner", "-nostdin", *args]
    p = subprocess.run(cmd, cwd=cwd, capture_output=capture, creationflags=_NO_WINDOW)
    if p.returncode != 0:
        tail = (p.stderr or b"").decode("utf-8", "replace")[-2500:]
        raise FFmpegError(f"ffmpeg gagal ({p.returncode}):\n{tail}")
    return p


@dataclass
class Probe:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool


def probe(path: str | Path) -> Probe:
    """Baca info video dari stderr `ffmpeg -i` (tidak butuh ffprobe)."""
    p = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, creationflags=_NO_WINDOW)
    err = p.stderr.decode("utf-8", "replace")
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if not m:
        raise FFmpegError(f"Bukan file video yang valid: {path}\n{err[-800:]}")
    dur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    v = re.search(r"Stream #.*Video:.*?(\d{2,5})x(\d{2,5})", err)
    if not v:
        raise FFmpegError("File tidak punya stream video.")
    f = re.search(r"(\d+(?:\.\d+)?) fps", err)
    w, h = int(v[1]), int(v[2])
    rot = re.search(r"rotate\s*:\s*(-?\d+)|rotation of (-?\d+)", err)
    if rot and abs(int(rot[1] or rot[2])) in (90, 270):
        w, h = h, w
    return Probe(dur, w, h, float(f[1]) if f else 30.0, "Audio:" in err)


def extract_audio(src: Path, dst: Path) -> Path:
    run(["-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)])
    return dst


def audio_energy(wav: Path, hop: float = 0.5) -> np.ndarray:
    """RMS per `hop` detik, dinormalisasi 0..1 — dipakai untuk skor momen."""
    import wave

    with wave.open(str(wav), "rb") as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    n = int(16000 * hop)
    if raw.size < n:
        return np.zeros(1)
    frames = raw[: raw.size // n * n].reshape(-1, n)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    lo, hi = np.percentile(rms, 5), np.percentile(rms, 98)
    return np.clip((rms - lo) / max(hi - lo, 1e-6), 0, 1)


def grab_frame(src: Path, t: float, dst: Path, width: int = 960) -> Path:
    run(["-y", "-ss", f"{max(t, 0):.3f}", "-i", str(src), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(dst)])
    return dst
