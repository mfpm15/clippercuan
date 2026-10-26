"""Ambil video sumber: link (YouTube dan situs lain yang didukung yt-dlp) atau file lokal."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from .config import FFMPEG


def is_url(s: str) -> bool:
    return s.strip().lower().startswith(("http://", "https://"))


def fetch(source: str, out_dir: Path, progress: Callable[[float, str], None] = lambda p, m: None) -> tuple[Path, str]:
    """Kembalikan (path video, judul sumber)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if not is_url(source):
        src = Path(source).expanduser()
        if not src.is_file():
            raise FileNotFoundError(f"File tidak ditemukan: {src}")
        dst = out_dir / ("source" + src.suffix.lower())
        if src.resolve() != dst.resolve():
            progress(0.5, "Menyalin file…")
            shutil.copy2(src, dst)
        return dst, src.stem.split("__", 1)[-1]  # unggahan: "<id>__<nama asli>"

    import yt_dlp

    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                progress(d.get("downloaded_bytes", 0) / total, f"Mengunduh {d.get('_percent_str', '').strip()}")

    opts = {
        "outtmpl": str(out_dir / "source.%(ext)s"),
        # maks 1080p, gabung jadi mp4 agar cepat dipotong
        "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b",
        "merge_output_format": "mp4",
        "ffmpeg_location": FFMPEG,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "retries": 5,
        "fragment_retries": 5,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source.strip(), download=True)
    files = sorted(out_dir.glob("source.*"), key=lambda p: p.stat().st_size, reverse=True)
    files = [f for f in files if f.suffix not in (".part", ".ytdl")]
    if not files:
        raise RuntimeError("Unduhan selesai tetapi file video tidak ditemukan.")
    return files[0], info.get("title") or "Video"
