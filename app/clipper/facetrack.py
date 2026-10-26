"""Smart crop → keyframe posisi crop horizontal yang halus.

Urutan prioritas per sampel frame:
  1. Satu wajah            → ikuti wajah itu.
  2. Dua wajah atau lebih  → ikuti PEMBICARA AKTIF (gerakan area mulut paling tinggi),
                             dengan histeresis agar kamera tidak bolak-balik.
  3. Tidak ada wajah       → ikuti pusat GERAKAN (gameplay, produk, olahraga).
  4. Tidak ada gerakan     → tahan posisi terakhir.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .config import FFMPEG
from .media import _NO_WINDOW

SAMPLE_FPS = 4.0
_W = 480


YUNET = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"


class _Detector:
    """YuNet (akurat, dengan titik mulut) bila tersedia; cadangan Haar cascade."""

    def __init__(self, w: int, h: int):
        import cv2

        self.cv2 = cv2
        self.yunet = None
        if YUNET.is_file() and hasattr(cv2, "FaceDetectorYN"):
            try:
                self.yunet = cv2.FaceDetectorYN.create(str(YUNET), "", (w, h), 0.75, 0.3, 50)
            except Exception as e:  # noqa: BLE001
                print(f"[smart crop] YuNet gagal dimuat ({e}); pakai Haar")
        if self.yunet is None:
            self.haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            if self.haar.empty():
                raise RuntimeError("detektor wajah tidak tersedia")

    def __call__(self, gray: np.ndarray) -> list[tuple[int, int, int, int, tuple | None]]:
        """[(x, y, w, h, mouth_box|None)] dalam piksel."""
        h = gray.shape[0]
        if self.yunet is not None:
            _, faces = self.yunet.detect(self.cv2.cvtColor(gray, self.cv2.COLOR_GRAY2BGR))
            out = []
            for f in faces if faces is not None else []:
                x, y, w, hh = (int(v) for v in f[:4])
                rmx, rmy, lmx, lmy = f[10], f[11], f[12], f[13]  # sudut mulut kanan & kiri
                mw = max(abs(lmx - rmx), w * 0.25)
                cx, cy = (rmx + lmx) / 2, (rmy + lmy) / 2
                mouth = (int(cx - mw * 0.7), int(cy - mw * 0.45), int(cx + mw * 0.7), int(cy + mw * 0.55))
                out.append((max(x, 0), max(y, 0), w, hh, mouth))
            return out
        faces = self.haar.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=6, minSize=(max(h // 14, 16),) * 2)
        return [(int(x), int(y), int(w), int(hh), None) for x, y, w, hh in faces]


def _frames(src: Path, start: float, end: float, src_w: int, src_h: int) -> np.ndarray:
    h = int(round(_W * src_h / src_w / 2) * 2)
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
           "-vf", f"fps={SAMPLE_FPS},scale={_W}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.run(cmd, capture_output=True, creationflags=_NO_WINDOW)
    buf = np.frombuffer(p.stdout, dtype=np.uint8)
    n = buf.size // (_W * h)
    return buf[: n * _W * h].reshape(n, h, _W) if n else np.zeros((0, h, _W), np.uint8)


def analyse(frames: np.ndarray) -> list[dict]:
    """Per frame: {"faces": [(cx, w, mouth_act)], "motion": cx|None} — semua dalam pecahan lebar."""
    n, h, w = frames.shape
    det = _Detector(w, h)
    out = []
    prev = None
    for f in frames:
        diff = np.abs(f.astype(np.int16) - prev.astype(np.int16)) if prev is not None else None
        items = []
        for x, y, fw, fh, mouth in det(f):
            act = 0.0
            if diff is not None:
                if mouth:
                    mx0, my0, mx1, my1 = (max(v, 0) for v in mouth)
                else:  # Haar: perkiraan area mulut ≈ 40% bawah kotak wajah
                    my0, my1 = y + int(fh * 0.62), y + int(fh * 1.05)
                    mx0, mx1 = x + int(fw * 0.2), x + int(fw * 0.8)
                region = diff[my0:min(my1, h), mx0:min(mx1, w)]
                # kurangi gerak kepala/kamera: bandingkan dengan area dahi
                fore = diff[y + int(fh * 0.08):y + int(fh * 0.3), x + int(fw * 0.25):x + int(fw * 0.75)]
                act = max(float(region.mean()) - float(fore.mean() if fore.size else 0), 0.0) if region.size else 0.0
            items.append(((x + fw / 2) / w, fw / w, act))
        motion = None
        if diff is not None and not items:
            col = (diff > 18).sum(axis=0).astype(np.float32)
            total = col.sum()
            if total > h * w * 0.004:  # cukup banyak piksel bergerak
                motion = float((col * np.arange(w)).sum() / total / w)
        out.append({"faces": items, "motion": motion})
        prev = f
    return out


def choose_targets(info: list[dict], switch_ratio: float = 1.4, hold: int = 3) -> list[float | None]:
    """Pilih target x per frame. Melacak 'track' wajah berdasar posisi, memilih pembicara aktif."""
    tracks: list[dict] = []          # {x, ema, seen}
    current: dict | None = None
    challenger, streak = None, 0
    xs: list[float | None] = []
    for i, fr in enumerate(info):
        for t in tracks:
            t["ema"] *= 0.7  # rata-rata bergerak: ~2 dtk memori aktivitas mulut
        visible = []
        for cx, fw, act in fr["faces"]:
            tr = min(tracks, key=lambda t: abs(t["x"] - cx), default=None)
            if tr is None or abs(tr["x"] - cx) > max(0.12, fw * 0.8):
                tr = {"x": cx, "ema": 0.0, "seen": i}
                tracks.append(tr)
            tr["x"] = tr["x"] * 0.5 + cx * 0.5
            tr["ema"] = tr["ema"] + 0.3 * act
            tr["seen"] = i
            visible.append(tr)
        tracks = [t for t in tracks if i - t["seen"] < SAMPLE_FPS * 3]  # lupakan wajah yang hilang > 3 dtk
        if current is not None and current not in tracks:
            current = None
        if not visible and current is None:
            xs.append(fr["motion"])
            continue
        # kandidat = wajah yang terlihat dalam 1,5 detik terakhir (deteksi wajah kecil sering putus-putus)
        recent = [t for t in tracks if i - t["seen"] <= SAMPLE_FPS * 1.5]
        if len(recent) <= 1:
            if recent:
                current, challenger, streak = recent[0], None, 0
        else:
            best = max(recent, key=lambda t: t["ema"])
            if current is None or current not in recent:
                current, challenger, streak = best, None, 0
            elif best is not current and best["ema"] > current["ema"] * switch_ratio + 0.05:
                streak = streak + 1 if challenger is best else 1
                challenger = best
                if streak >= hold:
                    current, challenger, streak = best, None, 0
            else:
                challenger, streak = None, 0
        xs.append(current["x"])
    return xs


def track(src: Path, start: float, end: float, src_w: int, src_h: int) -> list[list[float]]:
    """Kembalikan keyframe [[t_relatif, center_x_pecahan], ...]. Fallback: tengah."""
    frames = _frames(src, start, end, src_w, src_h)
    if len(frames) == 0:
        return [[0.0, 0.5]]
    try:
        info = analyse(frames)
    except Exception as e:  # noqa: BLE001 — OpenCV tanpa modul deteksi → crop tengah, render tetap jalan
        print(f"[smart crop] detektor wajah tidak tersedia ({e}); pakai crop tengah")
        return [[0.0, 0.5]]
    return smooth(choose_targets(info), src_w, src_h)


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
    k = 7
    pad = np.pad(arr, (k // 2, k // 2), mode="edge")
    med = np.array([np.median(pad[i:i + k]) for i in range(arr.size)])

    crop_frac = min(src_h * 9 / 16 / src_w, 1.0)  # lebar crop 9:16 relatif lebar sumber
    dead = crop_frac * 0.18
    keys = [[0.0, float(med[0])]]
    cur = med[0]
    for i, x in enumerate(med[1:], 1):
        if abs(x - cur) > dead:
            t = i / SAMPLE_FPS
            jump = abs(x - cur) > crop_frac * 0.9  # ganti pembicara → potong langsung, bukan geser
            keys.append([max(t - (0.04 if jump else 0.6), keys[-1][0] + 0.02), float(cur)])
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
