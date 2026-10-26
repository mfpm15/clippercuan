"""Smart crop: lacak wajah/subjek → keyframe posisi crop horizontal yang halus."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .config import FFMPEG
from .media import _NO_WINDOW

SAMPLE_FPS = 2.0
_W = 320


def _detector():
    import cv2

    return cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def track(src: Path, start: float, end: float, src_w: int, src_h: int) -> list[list[float]]:
    """Kembalikan keyframe [[t_relatif, center_x_pecahan], ...]. Fallback: tengah."""
    import cv2

    h = int(round(_W * src_h / src_w / 2) * 2)
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
           "-vf", f"fps={SAMPLE_FPS},scale={_W}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.run(cmd, capture_output=True, creationflags=_NO_WINDOW)
    buf = np.frombuffer(p.stdout, dtype=np.uint8)
    n = buf.size // (_W * h)
    if n == 0:
        return [[0.0, 0.5]]
    frames = buf[: n * _W * h].reshape(n, h, _W)
    try:
        det = _detector()
        if det.empty():
            raise RuntimeError("cascade kosong")
    except Exception as e:  # OpenCV tanpa modul deteksi → crop tengah, render tetap jalan
        print(f"[smart crop] detektor wajah tidak tersedia ({e}); pakai crop tengah")
        return [[0.0, 0.5]]
    xs: list[float | None] = []
    for f in frames:
        faces = det.detectMultiScale(f, scaleFactor=1.15, minNeighbors=5, minSize=(max(h // 12, 18),) * 2)
        if len(faces):
            x, y, w, hh = max(faces, key=lambda r: r[2] * r[3])  # wajah terbesar = pembicara utama
            xs.append((x + w / 2) / _W)
        else:
            xs.append(None)
    return smooth(xs, src_w, src_h)


def smooth(xs: list[float | None], src_w: int, src_h: int) -> list[list[float]]:
    """Isi celah, median filter, lalu 'dead zone' agar kamera tidak goyang."""
    known = [x for x in xs if x is not None]
    if not known:
        return [[0.0, 0.5]]
    filled, last = [], known[0]
    for x in xs:
        last = x if x is not None else last
        filled.append(last)
    arr = np.array(filled)
    k = 5
    pad = np.pad(arr, (k // 2, k // 2), mode="edge")
    med = np.array([np.median(pad[i:i + k]) for i in range(arr.size)])

    crop_frac = min(src_h * 9 / 16 / src_w, 1.0)  # lebar crop 9:16 relatif lebar sumber
    dead = crop_frac * 0.18
    keys = [[0.0, float(med[0])]]
    cur = med[0]
    for i, x in enumerate(med[1:], 1):
        if abs(x - cur) > dead:
            t = i / SAMPLE_FPS
            keys.append([max(t - 0.6, keys[-1][0] + 0.1), float(cur)])  # tahan, lalu geser halus ~0.6 dtk
            keys.append([t, float(x)])
            cur = x
    return [[round(t, 2), round(x, 4)] for t, x in keys]


def x_expr(keys: list[list[float]], src_w: int, crop_w: int) -> str:
    """Ekspresi ffmpeg piecewise-linear untuk posisi x crop (pixel), dibatasi tepi frame."""
    def px(cx):
        return max(0.0, min(src_w - crop_w, cx * src_w - crop_w / 2))

    keys = sorted(keys, key=lambda k: k[0]) or [[0, 0.5]]
    expr = f"{px(keys[-1][1]):.1f}"
    for (t0, x0), (t1, x1) in reversed(list(zip(keys, keys[1:]))):
        a, b = px(x0), px(x1)
        seg = f"{a:.1f}+({b - a:.1f})*(t-{t0:.2f})/{max(t1 - t0, 0.01):.2f}"
        expr = f"if(lt(t,{t1:.2f}),{seg},{expr})"
    return f"if(lt(t,{keys[0][0]:.2f}),{px(keys[0][1]):.1f},{expr})"
