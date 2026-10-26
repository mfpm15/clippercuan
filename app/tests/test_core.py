"""Tes cepat tanpa video: python -m pytest app/tests  (atau: python app/tests/test_core.py)."""
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("CLIPPER_HOME", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from clipper import captions, highlights, render  # noqa: E402
from clipper.config import DEFAULTS, deep_merge  # noqa: E402


def _words(text, start=0.0, step=0.4, gap_every=0, gap=1.5):
    out, t = [], start
    for i, w in enumerate(text.split()):
        if gap_every and i and i % gap_every == 0:
            t += gap
        out.append({"w": w, "s": round(t, 2), "e": round(t + step * 0.8, 2), "p": 0.9})
        t += step
    return out


def _events(ass, style):
    rows = []
    for line in ass.splitlines():
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            if parts[3] == style:
                to = lambda s: sum(float(x) * m for x, m in zip(s.split(":"), (3600, 60, 1)))  # noqa: E731
                rows.append((to(parts[1]), to(parts[2]), parts[9]))
    return rows


def test_caption_lines_never_overlap():
    words = _words("kenapa banyak usaha kecil gagal di tahun pertama ini rahasia yang jarang dibahas orang", gap_every=4, gap=0.3)
    for style in ("box", "karaoke", "clean", "wbw"):
        cfg = deep_merge(DEFAULTS, {"caption": {"style": style}})
        ev = sorted(_events(captions.build_ass(words, "Judul", cfg, (1080, 1920), 10), "Cap"))
        for (s1, e1, _), (s2, _, _) in zip(ev, ev[1:]):
            assert e1 <= s2 + 0.011, f"{style}: baris bertumpuk {e1} > {s2}"


def test_box_layer_matches_text_layer():
    words = _words("satu dua tiga empat lima enam")
    ass = captions.build_ass(words, "", DEFAULTS, (1080, 1920), 5)
    text, box = _events(ass, "Cap"), _events(ass, "CapBox")
    assert len(text) == len(box) > 0
    strip = lambda s: re.sub(r"\{[^}]*\}", "", s)  # noqa: E731
    assert [strip(t[2]) for t in text] == [strip(b[2]) for b in box]


def test_word_style_and_escape():
    words = _words("halo {dunia} keren")
    words[2]["style"] = {"color": "#00ff00", "scale": 1.5}
    ass = captions.build_ass(words, "Judul {aneh}", deep_merge(DEFAULTS, {"caption": {"style": "clean"}}), (1080, 1920), 3)
    assert "{dunia}" not in ass and "{aneh}" not in ass
    ass2 = captions.build_ass(words, "", DEFAULTS, (1080, 1920), 3)
    assert r"\c&H0000FF00" in ass2 and r"\fscx150" in ass2


def test_srt_format():
    srt = captions.build_srt(_words("a b c d e f g h"), 3)
    assert srt.startswith("1\n00:00:00,000 --> ")
    assert re.search(r"\n2\n00:00:0\d,\d{3} --> ", srt)


def test_cut_plan_and_remap():
    words = _words("a b c d e f", gap_every=3, gap=2.0)
    plan = render.cut_plan(words, 6.0)
    assert len(plan) == 2
    kept = sum(b - a for a, b in plan)
    assert kept < 6.0 - 1.5
    assert render.remap(words[3]["s"], plan) < words[3]["s"] - 1.5
    assert render.remap(0, plan) == 0


def test_moments_non_overlapping_and_sorted():
    segs, words, t = [], [], 0.0
    sentences = ["Kenapa banyak orang gagal?", "Ini rahasia yang jarang dibahas.", "Tips pertama pisahkan uang.",
                 "Jangan lupa catat semua.", "Kesalahan terbesar adalah malas.", "Terima kasih sudah menonton."] * 6
    for s in sentences:
        ws = _words(s, t, 0.35)
        idx = list(range(len(words), len(words) + len(ws)))
        words += ws
        segs.append({"text": s, "s": ws[0]["s"], "e": ws[-1]["e"], "words": idx})
        t = ws[-1]["e"] + 0.3
    tr = {"segments": segs, "words": words, "language": "id"}
    ms = highlights.find_moments(tr, np.random.rand(int(t * 2) + 1), t, 4, 8, 20)
    assert 1 <= len(ms) <= 4
    assert [m["score"] for m in ms] == sorted((m["score"] for m in ms), reverse=True)
    for a in ms:
        assert a["reason"] and a["title"]
        for b in ms:
            if a is not b:
                assert min(a["end"], b["end"]) - max(a["start"], b["start"]) < 0.2 * (a["end"] - a["start"]) + 0.5
    kit = highlights.post_kit(ms[0]["text"], ms[0]["title"], "id")
    assert kit["hashtags"] and all(h.startswith("#") for h in kit["hashtags"])


def test_fallback_without_speech():
    ms = highlights.find_moments({"segments": [], "words": []}, np.zeros(1), 120, 3, 20, 40)
    assert len(ms) == 3 and all(m["end"] - m["start"] >= 20 for m in ms)


def test_active_speaker_switch_and_motion_fallback():
    from clipper import facetrack

    # 0-10 dtk: kiri bicara, 10-20 dtk: kanan bicara (4 sampel/dtk); deteksi kanan putus-putus
    info = []
    for i in range(80):
        left_talk = i < 40
        faces = [(0.25, 0.14, 8.0 if left_talk else 0.1)]
        if i % 3:  # wajah kanan kadang tidak terdeteksi
            faces.append((0.74, 0.09, 0.0 if left_talk else 0.8))
        info.append({"faces": faces, "motion": None})
    xs = facetrack.choose_targets(info)
    assert all(abs(x - 0.25) < 0.02 for x in xs[2:40]), "harus tetap di kiri saat kiri bicara"
    switch = next(i for i, x in enumerate(xs) if i > 40 and abs(x - 0.74) < 0.03)
    assert switch < 40 + 4 * 5, f"harus pindah ke kanan < 5 dtk, terjadi di sampel {switch}"
    assert all(abs(x - 0.74) < 0.03 for x in xs[switch:]), "tidak boleh bolak-balik"
    # tanpa wajah → ikuti gerakan
    xs2 = facetrack.choose_targets([{"faces": [], "motion": 0.2 + i * 0.01} for i in range(20)])
    assert xs2[0] == 0.2 and abs(xs2[-1] - 0.39) < 1e-6
    keys = facetrack.smooth(xs, 1280, 720)
    assert keys[0][1] < 0.3 and keys[-1][1] > 0.7


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("OK  ", name)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print("FAIL", name, e)
    sys.exit(1 if fails else 0)
