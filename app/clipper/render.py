"""Render satu klip: potong → framing (crop/blur/split) → caption/judul/watermark → MP4 H.264."""
from __future__ import annotations

from pathlib import Path

from . import captions, effects, facetrack
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


def cut_plan(words: list[dict], dur: float, gap: float = 0.55, pad: float = 0.12) -> list[tuple[float, float]]:
    """Rentang yang dipertahankan saat 'potong jeda hening' (berdasar timestamp kata)."""
    if not words:
        return [(0.0, dur)]
    ranges: list[list[float]] = []
    for w in words:
        a, b = max(0.0, w["s"] - pad), min(dur, w["e"] + pad)
        if ranges and a - ranges[-1][1] < gap:
            ranges[-1][1] = max(ranges[-1][1], b)
        else:
            ranges.append([a, b])
    ranges[0][0] = 0.0 if ranges[0][0] < 0.4 else ranges[0][0]
    return [(round(a, 3), round(b, 3)) for a, b in ranges if b - a > 0.05]


def remap(t: float, plan: list[tuple[float, float]]) -> float:
    """Waktu di klip asli → waktu setelah jeda dipotong."""
    acc = 0.0
    for a, b in plan:
        if t < a:
            return acc
        if t <= b:
            return acc + t - a
        acc += b - a
    return acc


def framing_filter(layout: str, pr: Probe, cfg: dict, keys: list | None, inp: str = "0:v") -> str:
    """Filtergraph dari [inp] ke [fr]."""
    Wt, Ht = SIZES[layout]
    W, H = pr.width, pr.height
    if layout in ("portrait", "square"):
        a = Wt / Ht
        if W / H > a:  # sumber lebih lebar → crop horizontal (bisa ikut wajah)
            cw = _even(H * a)
            x = facetrack.x_expr(keys, W, cw) if keys else f"{(W - cw) / 2:.1f}"
            return f"[{inp}]crop=w={cw}:h={H}:x='{x}':y=0,scale={Wt}:{Ht}:flags=lanczos,setsar=1[fr]"
        ch = _even(W / a)
        return f"[{inp}]crop=w={W}:h={ch}:x=0:y={(H - ch) / 2:.1f},scale={Wt}:{Ht}:flags=lanczos,setsar=1[fr]"
    if layout == "blur":
        return (f"[{inp}]split[a][b];[a]scale={Wt}:{Ht}:force_original_aspect_ratio=increase,crop={Wt}:{Ht},"
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

        return (f"[{inp}]split[a][b];[a]{rect(sp['face'])},scale={Wt}:{hf}:force_original_aspect_ratio=increase,crop={Wt}:{hf}[top];"
                f"[b]{rect(sp['game'])},scale={Wt}:{hg}:force_original_aspect_ratio=increase,crop={Wt}:{hg}[bot];"
                f"[top][bot]vstack,setsar=1[fr]")
    # landscape
    return (f"[{inp}]scale={Wt}:{Ht}:force_original_aspect_ratio=decrease:flags=lanczos,"
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

    # potong jeda hening: susun ulang waktu kata & keyframe ke timeline baru
    plan = cut_plan(cw, dur, float(cfg.get("silence_gap", 0.55))) if cfg.get("cut_silence") and cw else [(0.0, dur)]
    cut = len(plan) > 1 or plan[0][0] > 0.01 or plan[0][1] < dur - 0.01
    out_dur = sum(b - a for a, b in plan)
    sub_words = [{**w, "s": round(remap(w["s"], plan), 3), "e": round(remap(w["e"], plan), 3)} for w in cw] if cut else cw
    sub_keys = [[round(remap(t, plan), 2), x] for t, x in keys] if (cut and keys) else keys

    ass_name = f"{cid}.ass"
    (work / ass_name).write_text(captions.build_ass(sub_words, clip.get("title", ""), cfg, size, out_dur), "utf-8")
    (work / f"{cid}.srt").write_text(captions.build_srt(sub_words, int(cfg["caption"].get("words_per_line", 3))), "utf-8")

    wm = cfg["watermark"]
    use_img = wm["enabled"] and wm.get("image") and Path(wm["image"]).is_file()
    if cut:
        n = len(plan)
        vs = "".join(f"[cv{i}]" for i in range(n))
        graph = (f"[0:v]split={n}{vs};" if n > 1 else "[0:v]null[cv0];")
        graph += "".join(f"[cv{i}]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}];" for i, (a, b) in enumerate(plan))
        if pr.has_audio:
            as_ = "".join(f"[ca{i}]" for i in range(n))
            graph += (f"[0:a:0]asplit={n}{as_};" if n > 1 else "[0:a:0]anull[ca0];")
            graph += "".join(f"[ca{i}]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}];" for i, (a, b) in enumerate(plan))
            graph += "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac];"
        else:
            graph += "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc];"
        graph += framing_filter(layout, pr, cfg, sub_keys, "vc")
    else:
        graph = framing_filter(layout, pr, cfg, keys)
    fonts = f":fontsdir={_fpath(FONTS_DIR)}" if FONTS_DIR.is_dir() else ""
    graph += f";[fr]ass=filename={ass_name}{fonts}[cap]"
    last = "cap"
    extra_inputs: list[list[str]] = []

    def add_input(opts: list[str]) -> int:
        extra_inputs.append(opts)
        return len(extra_inputs)  # indeks input ffmpeg (0 = video sumber)

    W, H = size
    if use_img:
        idx = add_input(["-i", str(wm["image"])])
        mw = int(W * 0.18 * wm.get("size", 42) / 42)
        m = 40
        pos = {"tl": f"{m}:{m}", "tr": f"W-w-{m}:{m}", "bl": f"{m}:H-h-{m}", "br": f"W-w-{m}:H-h-{m}", "c": "(W-w)/2:(H-h)/2"}[wm.get("position", "br")]
        graph += (f";[{idx}:v]scale={mw}:-1,format=rgba,colorchannelmixer=aa={float(wm.get('opacity', .8)):.2f}[wm];"
                  f"[{last}][wm]overlay={pos}[wmo]")
        last = "wmo"

    # emoji otomatis dari kata kunci (PNG di atas caption, muncul halus)
    emojis = effects.plan_emojis(sub_words, out_dur) if cfg.get("emoji", {}).get("enabled") else []
    if emojis:
        es = int(170 * W / 1080 * float(cfg["emoji"].get("size", 1.0)))
        cap_pos = cfg["caption"].get("position", "bottom")
        ey = {"bottom": int(H * 0.60), "middle": int(H * 0.36), "top": int(H * 0.30)}[cap_pos] - es
        for k, em in enumerate(emojis):
            idx = add_input(["-loop", "1", "-framerate", "30", "-t", f"{em['e'] + 0.2:.2f}", "-i", em["file"]])
            d = em["e"] - em["s"]
            graph += (f";[{idx}:v]scale={es}:{es},format=rgba,fade=t=in:st={em['s']:.2f}:d=0.15:alpha=1,"
                      f"fade=t=out:st={em['s'] + d - 0.2:.2f}:d=0.2:alpha=1[em{k}];"
                      f"[{last}][em{k}]overlay=x=(W-w)/2:y={ey}:eof_action=pass:enable='between(t,{em['s']:.2f},{em['e']:.2f})'[e{k}]")
            last = f"e{k}"

    # progress bar tipis yang berjalan sepanjang klip
    pb = cfg.get("progress_bar", {})
    if pb.get("enabled"):
        ph = max(int(pb.get("height", 12) * W / 1080), 4)
        col = "0x" + pb.get("color", "#FFC933").lstrip("#")[:6]
        y = "0" if pb.get("position") == "top" else f"{H - ph}"
        graph += (f";color=c={col}:s={W}x{ph}:r=30:d={out_dur:.3f}[pbar];"
                  f"[{last}][pbar]overlay=x='-w+w*t/{out_dur:.3f}':y={y}:eof_action=pass[pbo]")
        last = "pbo"

    # audio: suara asli (+ potong jeda) dan musik latar dengan ducking otomatis
    mu = cfg.get("music", {})
    music_file = mu.get("file") if mu.get("enabled") else None
    use_music = bool(music_file) and Path(music_file).is_file()
    orig = ("[ac]" if cut else "[0:a:0]") if pr.has_audio else None
    audio_map = None
    if use_music:
        idx = add_input(["-stream_loop", "-1", "-i", str(music_file)])
        vol = float(mu.get("volume", 0.15))
        fade_out = max(out_dur - 1.5, 0)
        graph += (f";[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={vol:.3f},atrim=0:{out_dur:.3f},"
                  f"afade=t=in:d=0.8,afade=t=out:st={fade_out:.2f}:d=1.5[mus]")
        if orig and mu.get("duck", True):
            graph += (f";{orig}aformat=sample_rates=48000:channel_layouts=stereo,asplit[o1][o2];"
                      f"[mus][o2]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[dk];"
                      f"[o1][dk]amix=inputs=2:duration=first:normalize=0[aout]")
        elif orig:
            graph += f";{orig}aformat=sample_rates=48000:channel_layouts=stereo[o1];[o1][mus]amix=inputs=2:duration=first:normalize=0[aout]"
        else:
            graph += ";[mus]anull[aout]"
        audio_map = "[aout]"
    elif orig:
        audio_map = "[ac]" if cut else "0:a:0?"

    out = work / f"{cid}.mp4"
    tmp = work / f"{cid}.tmp.mp4"
    args = ["-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src)]
    for opts in extra_inputs:
        args += opts
    args += ["-filter_complex", graph, "-map", f"[{last}]"]
    if audio_map:
        args += ["-map", audio_map, "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
    else:
        args += ["-an"]
    args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-r", f"{min(pr.fps, 60):.3f}", "-movflags", "+faststart", "-t", f"{out_dur:.3f}", tmp.name]
    run(args, cwd=work)
    tmp.replace(out)
    grab_frame(out, min(1.0, out_dur / 2), work / f"{cid}.jpg", width=360)
    return {"file": out.name, "thumb": f"{cid}.jpg", "srt": f"{cid}.srt", "crop_keys": keys, "words": cw,
            "duration": round(out_dur, 2), "cut_saved": round(dur - out_dur, 2), "emojis": [e["code"] for e in emojis]}
