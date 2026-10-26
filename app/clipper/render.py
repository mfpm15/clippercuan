"""Render satu klip: potong → framing (crop/blur/split) → caption/judul/watermark → MP4 H.264."""
from __future__ import annotations

from pathlib import Path

from . import captions, facetrack
from .config import FONTS_DIR, SIZES
from .media import Probe, grab_frame, run


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def _fpath(p: Path | str) -> str:
    """Path aman untuk argumen filter ffmpeg (Windows: C\\:/...)."""
    return "'" + str(p).replace("\\", "/").replace(":", "\\:").replace("'", r"\'") + "'"


def clip_words(words: list[dict], start: float, end: float) -> list[dict]:
    return [{"w": w["w"], "s": round(w["s"] - start, 3), "e": round(w["e"] - start, 3)}
            for w in words if w["s"] >= start - 0.05 and w["e"] <= end + 0.3]


def framing_filter(layout: str, pr: Probe, cfg: dict, keys: list | None) -> str:
    """Filtergraph dari [0:v] ke [fr]."""
    Wt, Ht = SIZES[layout]
    W, H = pr.width, pr.height
    if layout in ("portrait", "square"):
        a = Wt / Ht
        if W / H > a:  # sumber lebih lebar → crop horizontal (bisa ikut wajah)
            cw = _even(H * a)
            x = facetrack.x_expr(keys, W, cw) if keys else f"{(W - cw) / 2:.1f}"
            return f"[0:v]crop=w={cw}:h={H}:x='{x}':y=0,scale={Wt}:{Ht}:flags=lanczos,setsar=1[fr]"
        ch = _even(W / a)
        return f"[0:v]crop=w={W}:h={ch}:x=0:y={(H - ch) / 2:.1f},scale={Wt}:{Ht}:flags=lanczos,setsar=1[fr]"
    if layout == "blur":
        return (f"[0:v]split[a][b];[a]scale={Wt}:{Ht}:force_original_aspect_ratio=increase,crop={Wt}:{Ht},"
                f"boxblur=24:3,eq=brightness=-0.07:saturation=1.2[bg];"
                f"[b]scale={Wt}:{Ht}:force_original_aspect_ratio=decrease:flags=lanczos[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[fr]")
    if layout == "split":
        sp = cfg["split"]
        hf = _even(Ht * float(sp.get("face_ratio", 0.4)))
        hg = Ht - hf

        def rect(r):
            x, y, w, h = [float(v) for v in r]
            w, h = max(min(w, 1 - x), 0.05), max(min(h, 1 - y), 0.05)
            return f"crop={_even(W * w)}:{_even(H * h)}:{int(W * x)}:{int(H * y)}"

        return (f"[0:v]split[a][b];[a]{rect(sp['face'])},scale={Wt}:{hf}:force_original_aspect_ratio=increase,crop={Wt}:{hf}[top];"
                f"[b]{rect(sp['game'])},scale={Wt}:{hg}:force_original_aspect_ratio=increase,crop={Wt}:{hg}[bot];"
                f"[top][bot]vstack,setsar=1[fr]")
    # landscape
    return (f"[0:v]scale={Wt}:{Ht}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad={Wt}:{Ht}:(ow-iw)/2:(oh-ih)/2,setsar=1[fr]")


def render_clip(work: Path, src: Path, pr: Probe, clip: dict, cfg: dict, words: list[dict]) -> dict:
    """Tulis clip_XX.mp4 + .jpg di `work`; kembalikan field yang diperbarui."""
    cid = clip["id"]
    start, end = float(clip["start"]), float(clip["end"])
    dur = max(end - start, 0.5)
    layout = cfg["layout"]
    size = SIZES[layout]

    keys = clip.get("crop_keys")
    if layout in ("portrait", "square") and cfg.get("smart_crop") and not keys and pr.width / pr.height > size[0] / size[1]:
        keys = facetrack.track(src, start, end, pr.width, pr.height)
    cw = clip_words(words, start, end) if clip.get("words") is None else clip["words"]

    ass_name = f"{cid}.ass"
    (work / ass_name).write_text(captions.build_ass(cw, clip.get("title", ""), cfg, size, dur), "utf-8")

    wm = cfg["watermark"]
    use_img = wm["enabled"] and wm.get("image") and Path(wm["image"]).is_file()
    graph = framing_filter(layout, pr, cfg, keys)
    fonts = f":fontsdir={_fpath(FONTS_DIR)}" if FONTS_DIR.is_dir() else ""
    graph += f";[fr]ass=filename={ass_name}{fonts}[cap]"
    last = "cap"
    if use_img:
        mw = int(size[0] * 0.18 * wm.get("size", 42) / 42)
        m = 40
        pos = {"tl": f"{m}:{m}", "tr": f"W-w-{m}:{m}", "bl": f"{m}:H-h-{m}", "br": f"W-w-{m}:H-h-{m}", "c": "(W-w)/2:(H-h)/2"}[wm.get("position", "br")]
        graph += (f";[1:v]scale={mw}:-1,format=rgba,colorchannelmixer=aa={float(wm.get('opacity', .8)):.2f}[wm];"
                  f"[cap][wm]overlay={pos}[out]")
        last = "out"

    out = work / f"{cid}.mp4"
    tmp = work / f"{cid}.tmp.mp4"
    args = ["-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src)]
    if use_img:
        args += ["-i", str(wm["image"])]
    args += ["-filter_complex", graph, "-map", f"[{last}]"]
    args += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "160k", "-ar", "48000"] if pr.has_audio else ["-an"]
    args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-r", f"{min(pr.fps, 60):.3f}", "-movflags", "+faststart", "-t", f"{dur:.3f}", tmp.name]
    run(args, cwd=work)
    tmp.replace(out)
    grab_frame(out, min(1.0, dur / 2), work / f"{cid}.jpg", width=360)
    return {"file": out.name, "thumb": f"{cid}.jpg", "crop_keys": keys, "words": cw, "duration": round(dur, 2)}
