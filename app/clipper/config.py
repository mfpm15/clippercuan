"""Lokasi data, binary ffmpeg, dan nilai default."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "ClipperCuan"
PKG_DIR = Path(__file__).resolve().parent
WEB_DIR = PKG_DIR / "web"
FONTS_DIR = PKG_DIR / "fonts"

DATA_DIR = Path(os.environ.get("CLIPPER_HOME", Path.home() / APP_NAME)).expanduser()
PROJECTS_DIR = DATA_DIR / "projects"
MODELS_DIR = DATA_DIR / "models"
UPLOADS_DIR = DATA_DIR / "uploads"
for d in (PROJECTS_DIR, MODELS_DIR, UPLOADS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _find_ffmpeg() -> str:
    env = os.environ.get("CLIPPER_FFMPEG")
    if env:
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:  # ffmpeg bawaan paket pip, jadi pengguna tidak perlu memasang manual
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover
        sys.exit("ffmpeg tidak ditemukan. Jalankan installer (start) ulang atau pasang ffmpeg.")


FFMPEG = _find_ffmpeg()

# Default pipeline — semua bisa diubah dari UI per proyek.
DEFAULTS: dict = {
    "language": "auto",          # auto | id | en | ms | ar | ja | ko | es | ...
    "translate_en": False,       # caption diterjemahkan ke Inggris (Whisper translate)
    "model": "small",            # tiny | base | small | medium | large-v3
    "clip_count": 6,
    "min_sec": 20,
    "max_sec": 60,
    "layout": "portrait",        # portrait | square | blur | split | landscape
    "smart_crop": True,          # ikuti wajah
    "split": {                   # area dalam pecahan (0..1) dari frame sumber
        "face": [0.70, 0.62, 0.30, 0.38],   # x, y, w, h  (default: facecam pojok kanan bawah)
        "game": [0.0, 0.0, 1.0, 1.0],
        "face_ratio": 0.4,       # porsi tinggi frame output untuk facecam (atas)
    },
    "caption": {
        "enabled": True,
        "style": "box",          # box | wbw | karaoke | clean
        "font": "Montserrat ExtraBold",
        "size": 82,
        "color": "#FFFFFF",
        "highlight": "#FFC933",
        "uppercase": True,
        "words_per_line": 3,
        "position": "bottom",    # bottom | middle | top
        "animation": "pop",      # pop | none
    },
    "title": {
        "enabled": True,
        "preset": "bar",         # bar | outline | neon | clean
        "duration": 0,           # detik; 0 = sepanjang klip
        "size": 70,
    },
    "watermark": {
        "enabled": False,
        "text": "@namakamu",
        "image": "",             # path gambar PNG (opsional)
        "position": "br",        # tl | tr | bl | br | c
        "opacity": 0.8,
        "size": 42,
    },
}

SIZES = {
    "portrait": (1080, 1920),
    "split": (1080, 1920),
    "blur": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}


def deep_merge(base: dict, extra: dict | None) -> dict:
    out = {k: (deep_merge(v, {}) if isinstance(v, dict) else v) for k, v in base.items()}
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out
