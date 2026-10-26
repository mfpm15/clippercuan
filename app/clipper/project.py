"""Proyek = satu video sumber + hasil klip. Disimpan sebagai JSON di ~/ClipperCuan/projects/<id>/."""
from __future__ import annotations

import json
import queue
import threading
import time
import traceback
import uuid
from pathlib import Path

from . import download, highlights, llm, media, render, transcribe
from .config import DEFAULTS, PROJECTS_DIR, deep_merge

_LOCK = threading.RLock()
_JOBS: "queue.Queue[tuple[str, str, dict]]" = queue.Queue()
_CANCEL: set[str] = set()


class Cancelled(Exception):
    pass


# ---------------------------------------------------------------- penyimpanan
def pdir(pid: str) -> Path:
    if not pid or any(c in pid for c in "/\\.") :
        raise KeyError(pid)
    return PROJECTS_DIR / pid


def load(pid: str) -> dict:
    f = pdir(pid) / "project.json"
    if not f.exists():
        raise KeyError(pid)
    with _LOCK:
        return json.loads(f.read_text("utf-8"))


def save(p: dict) -> None:
    with _LOCK:
        d = pdir(p["id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "project.json.tmp"
        tmp.write_text(json.dumps(p, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(d / "project.json")


def update(pid: str, **fields) -> dict:
    with _LOCK:
        p = load(pid)
        p.update(fields)
        p["updated"] = time.time()
        save(p)
        return p


def list_projects() -> list[dict]:
    out = []
    for f in PROJECTS_DIR.glob("*/project.json"):
        try:
            p = json.loads(f.read_text("utf-8"))
        except Exception:
            continue
        out.append({k: p.get(k) for k in ("id", "title", "status", "progress", "message", "created", "updated", "source")}
                   | {"clips": len(p.get("clips", [])), "thumb": next((c.get("thumb") for c in p.get("clips", []) if c.get("thumb")), None)})
    return sorted(out, key=lambda p: p.get("created") or 0, reverse=True)


def delete(pid: str) -> None:
    import shutil

    _CANCEL.add(pid)
    shutil.rmtree(pdir(pid), ignore_errors=True)


# ---------------------------------------------------------------- pembuatan
def create(source: str, settings: dict | None = None) -> dict:
    pid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    p = {
        "id": pid, "source": source, "title": "Memproses…", "status": "queued", "progress": 0.0,
        "message": "Menunggu antrean", "created": time.time(), "updated": time.time(),
        "settings": deep_merge(DEFAULTS, settings), "clips": [], "error": None,
    }
    save(p)
    _JOBS.put(("pipeline", pid, {}))
    return p


def cancel(pid: str) -> None:
    _CANCEL.add(pid)


def _progress(pid: str, lo: float, hi: float):
    last = [0.0]

    def cb(frac: float, msg: str):
        if pid in _CANCEL:
            raise Cancelled()
        now = time.time()
        if now - last[0] > 0.4 or frac >= 1:
            last[0] = now
            update(pid, progress=round(lo + (hi - lo) * max(0, min(frac, 1)), 3), message=msg)
    return cb


def _pipeline(pid: str) -> None:
    p = load(pid)
    cfg = p["settings"]
    work = pdir(pid)
    update(pid, status="running", message="Menyiapkan video…")

    src, title = download.fetch(p["source"], work, _progress(pid, 0.0, 0.18))
    pr = media.probe(src)
    update(pid, title=title, media={"file": src.name, "duration": pr.duration, "width": pr.width, "height": pr.height, "fps": pr.fps})

    wav = work / "audio.wav"
    if pr.has_audio:
        _progress(pid, 0.18, 0.2)(0, "Mengekstrak audio…")
        media.extract_audio(src, wav)
        tr = transcribe.load_or_transcribe(
            work / "transcript.json", wav, model_name=cfg["model"], language=cfg["language"],
            translate_en=cfg["translate_en"], progress=_progress(pid, 0.2, 0.62), duration=pr.duration)
        energy = media.audio_energy(wav)
    else:
        tr, energy = {"language": None, "words": [], "segments": []}, __import__("numpy").zeros(1)

    _progress(pid, 0.62, 0.65)(0, "Mencari momen paling menarik…")
    count, mn, mx = int(cfg["clip_count"]), float(cfg["min_sec"]), float(cfg["max_sec"])
    moments, engine = None, "lokal"
    if tr["segments"] and llm.active("moments") and cfg.get("use_llm", True):
        model = llm.cfg()["model_moments"]
        _progress(pid, 0.62, 0.65)(0.3, f"AI ({model}) memilih momen terbaik…")
        try:
            moments = _llm_moments(tr, energy, pr.duration, count, mn, mx)
            engine = model
        except Exception as e:  # noqa: BLE001 — selalu ada cadangan lokal
            print(f"[llm] gagal, pakai skor lokal: {e}")
            update(pid, llm_warning=f"AI tidak tersedia ({str(e)[:200]}). Dipakai skor lokal.")
    if not moments:
        moments = highlights.find_moments(tr, energy, pr.duration, count, mn, mx)
    update(pid, engine=engine)
    clips = [{"id": f"clip_{i + 1:02d}", **m, "status": "queued", "words": None, "crop_keys": None} for i, m in enumerate(moments)]
    update(pid, clips=clips, language=tr.get("language"))

    n = len(clips)
    for i, c in enumerate(clips):
        cb = _progress(pid, 0.65 + 0.35 * i / n, 0.65 + 0.35 * (i + 1) / n)
        cb(0, f"Render klip {i + 1}/{n}…")
        _render_one(pid, c["id"], tr["words"], pr)
    update(pid, status="done", progress=1.0, message=f"Selesai: {n} klip siap")


def _llm_moments(tr: dict, energy, duration: float, count: int, mn: float, mx: float) -> list[dict]:
    """Ambil ±30 kandidat beragam dari skor lokal, biarkan LLM memilih & memberi judul."""
    segs = tr["segments"]
    pool = highlights.non_overlapping(highlights.score_candidates(tr, energy, mn, mx), 30, max_overlap=0.5)
    pool.sort(key=lambda c: c["s"])
    picks = llm.pick_moments([{"id": i + 1, "start": c["s"], "end": c["e"], "text": c["text"]} for i, c in enumerate(pool)],
                             count, tr.get("language"))
    chosen, meta = [], {}
    for pk in sorted(picks, key=lambda x: -x["score"]):
        if 1 <= pk["id"] <= len(pool):
            c = pool[pk["id"] - 1]
            fits = all(min(c["e"], o["e"]) - max(c["s"], o["s"]) < 0.15 * (c["e"] - c["s"]) for o in chosen)
            if c not in chosen and fits:
                chosen.append(c)
                meta[id(c)] = pk
        if len(chosen) >= count:
            break
    out = [highlights.to_moment(c, segs, duration, meta[id(c)]["score"], meta[id(c)]["title"] or None,
                                reason=meta[id(c)]["reason"], hashtags=meta[id(c)]["hashtags"]) for c in chosen]
    if len(out) < count:  # model memilih terlalu sedikit → lengkapi dari skor lokal
        extra = highlights.non_overlapping(highlights.score_candidates(tr, energy, mn, mx), count, taken=chosen)[len(chosen):]
        out += [highlights.to_moment(c, segs, duration, 70) for c in extra]
    out.sort(key=lambda m: m["score"], reverse=True)
    return out


def _render_one(pid: str, cid: str, words: list[dict] | None = None, pr: media.Probe | None = None) -> None:
    p = load(pid)
    work = pdir(pid)
    src = work / p["media"]["file"]
    pr = pr or media.probe(src)
    if words is None:
        tf = work / "transcript.json"
        words = json.loads(tf.read_text("utf-8"))["words"] if tf.exists() else []
    clip = next(c for c in p["clips"] if c["id"] == cid)
    cfg = deep_merge(p["settings"], clip.get("overrides"))
    _set_clip(pid, cid, status="rendering")
    try:
        res = render.render_clip(work, src, pr, clip, cfg, words)
        _set_clip(pid, cid, status="done", error=None, version=int(time.time()), **res)
    except Exception as e:
        _set_clip(pid, cid, status="error", error=str(e)[-1500:])
        raise


def _set_clip(pid: str, cid: str, **fields) -> dict:
    with _LOCK:
        p = load(pid)
        for c in p["clips"]:
            if c["id"] == cid:
                c.update(fields)
                save(p)
                return c
    raise KeyError(cid)


# ---------------------------------------------------------------- edit klip
EDITABLE = {"title", "start", "end", "words", "crop_keys", "overrides"}


def edit_clip(pid: str, cid: str, changes: dict, rerender: bool = True) -> dict:
    changes = {k: v for k, v in changes.items() if k in EDITABLE}
    p = load(pid)
    clip = next((c for c in p["clips"] if c["id"] == cid), None)
    if clip is None:
        raise KeyError(cid)
    dur = p.get("media", {}).get("duration") or 1e9
    if "start" in changes or "end" in changes:
        s = max(0.0, float(changes.get("start", clip["start"])))
        e = min(dur, float(changes.get("end", clip["end"])))
        if e - s < 1:
            raise ValueError("Durasi klip minimal 1 detik")
        changes["start"], changes["end"] = round(s, 2), round(e, 2)
        if "words" not in changes:
            changes["words"] = None       # hitung ulang dari transkrip
        if "crop_keys" not in changes:
            changes["crop_keys"] = None
    if "overrides" in changes:
        changes["overrides"] = deep_merge(clip.get("overrides") or {}, changes["overrides"])
        lay = changes["overrides"].get("layout")
        if lay and lay != deep_merge(p["settings"], clip.get("overrides")).get("layout"):
            changes.setdefault("crop_keys", None)
    _set_clip(pid, cid, **changes, status="queued" if rerender else clip.get("status"))
    if rerender:
        _JOBS.put(("render", pid, {"cid": cid}))
    return load(pid)


def rerender_all(pid: str, settings: dict) -> dict:
    with _LOCK:
        p = load(pid)
        p["settings"] = deep_merge(p["settings"], settings)
        for c in p["clips"]:
            c["status"] = "queued"
            if "layout" in settings:
                c["crop_keys"] = None
        save(p)
    for c in p["clips"]:
        _JOBS.put(("render", pid, {"cid": c["id"]}))
    return p


# ---------------------------------------------------------------- worker
def _worker() -> None:
    while True:
        kind, pid, extra = _JOBS.get()
        try:
            if kind == "pipeline":
                _CANCEL.discard(pid)
                _pipeline(pid)
            elif kind == "render":
                _render_one(pid, extra["cid"])
        except Cancelled:
            safe_update(pid, status="cancelled", message="Dibatalkan")
        except KeyError:
            pass  # proyek dihapus saat antre
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            if kind == "pipeline":
                safe_update(pid, status="error", message=_friendly(e), error=traceback.format_exc()[-3000:])
        finally:
            _JOBS.task_done()


def safe_update(pid: str, **f) -> None:
    try:
        update(pid, **f)
    except Exception:
        pass


def _friendly(e: Exception) -> str:
    s = str(e)
    if "Sign in to confirm" in s or "bot" in s.lower():
        return "YouTube meminta verifikasi. Coba lagi nanti atau unduh videonya lalu pakai mode File."
    if "Unsupported URL" in s:
        return "Link tidak didukung. Pakai link YouTube/TikTok/Instagram atau unggah file."
    return s.splitlines()[0][:300] if s else e.__class__.__name__


def recover_interrupted() -> None:
    """Saat aplikasi dibuka lagi: tandai job yang terputus agar bisa diulang."""
    for f in PROJECTS_DIR.glob("*/project.json"):
        try:
            p = json.loads(f.read_text("utf-8"))
        except Exception:
            continue
        if p.get("status") in ("queued", "running"):
            p["status"], p["message"] = "error", "Terhenti karena aplikasi ditutup. Klik Ulangi."
            for c in p.get("clips", []):
                if c.get("status") in ("queued", "rendering"):
                    c["status"] = "error"
            save(p)


def retry(pid: str) -> dict:
    p = update(pid, status="queued", progress=0.0, message="Menunggu antrean", error=None)
    _JOBS.put(("pipeline", pid, {}))
    return p


_started = False


def start_worker() -> None:
    global _started
    if not _started:
        _started = True
        recover_interrupted()
        threading.Thread(target=_worker, daemon=True, name="clipper-worker").start()
