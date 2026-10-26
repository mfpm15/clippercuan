"""Otomatisasi untuk AI agent & alur kerja tanpa sentuhan:
  - webhook  : POST JSON ke URL saat proyek selesai / gagal
  - inbox    : taruh video di ~/ClipperCuan/inbox → otomatis diproses dengan template pilihan
  - export   : salin klip + SRT + caption posting ke folder tujuan saat selesai
"""
from __future__ import annotations

import json
import shutil
import threading
import time
import urllib.request
from pathlib import Path

from .config import DATA_DIR

INBOX_DIR = DATA_DIR / "inbox"
DONE_DIR = INBOX_DIR / "diproses"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".flv"}
for d in (INBOX_DIR, DONE_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _cfg() -> dict:
    from . import llm

    return llm.load_settings()["automation"]


def summary(p: dict) -> dict:
    """Ringkasan proyek yang ramah agent: path absolut ke semua hasil."""
    from . import project

    d = project.pdir(p["id"])
    clips = []
    for c in sorted(p.get("clips", []), key=lambda c: -(c.get("score") or 0)):
        post = c.get("post") or {}
        clips.append({
            "id": c["id"], "status": c.get("status"), "score": c.get("score"), "title": c.get("title"),
            "start": c.get("start"), "end": c.get("end"), "duration": c.get("duration"),
            "reason": c.get("reason"), "caption": post.get("caption"), "hashtags": post.get("hashtags", []),
            "video_path": str(d / c["file"]) if c.get("file") else None,
            "srt_path": str(d / c["srt"]) if c.get("srt") else None,
            "thumbnail_path": str(d / c["thumb"]) if c.get("thumb") else None,
            "error": c.get("error"),
        })
    return {"project_id": p["id"], "title": p.get("title"), "status": p.get("status"), "progress": p.get("progress"),
            "message": p.get("message"), "language": p.get("language"), "source": p.get("source"),
            "folder": str(d), "clips": clips}


def send_webhook(p: dict, event: str) -> None:
    url = (p.get("settings", {}).get("webhook_url") or _cfg().get("webhook_url") or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return

    def go():
        body = json.dumps({"event": event, **summary(p)}, ensure_ascii=False).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "ClipperCuan"})
        for attempt in range(3):
            try:
                urllib.request.urlopen(req, timeout=20).read()
                return
            except Exception as e:  # noqa: BLE001
                print(f"[webhook] gagal ({attempt + 1}/3): {e}")
                time.sleep(2 * (attempt + 1))

    threading.Thread(target=go, daemon=True).start()


def auto_export(p: dict) -> str | None:
    target = (p.get("settings", {}).get("export_dir") or _cfg().get("export_dir") or "").strip()
    if not target:
        return None
    from . import project

    safe = "".join(ch for ch in (p.get("title") or p["id"]) if ch.isalnum() or ch in " -_").strip()[:60] or p["id"]
    out = Path(target).expanduser() / f"{time.strftime('%Y-%m-%d')} {safe}"
    out.mkdir(parents=True, exist_ok=True)
    d = project.pdir(p["id"])
    lines = []
    for i, c in enumerate(sorted(p["clips"], key=lambda c: -(c.get("score") or 0)), 1):
        if c.get("status") != "done" or not c.get("file"):
            continue
        base = f"{i:02d} - " + ("".join(ch for ch in (c.get("title") or c["id"]) if ch.isalnum() or ch in " -_").strip()[:50] or c["id"])
        shutil.copy2(d / c["file"], out / f"{base}.mp4")
        if c.get("srt") and (d / c["srt"]).exists():
            shutil.copy2(d / c["srt"], out / f"{base}.srt")
        post = c.get("post") or {}
        lines.append(f"[{base}]\nJudul: {c.get('title', '')}\nCaption: {post.get('caption', '')}\nHashtag: {' '.join(post.get('hashtags', []))}\n")
    (out / "caption-posting.txt").write_text("\n".join(lines), "utf-8")
    return str(out)


def on_finished(pid: str, event: str) -> None:
    """Dipanggil worker setelah proyek selesai / gagal."""
    from . import project

    try:
        p = project.load(pid)
    except KeyError:
        return
    if event == "project.done":
        try:
            path = auto_export(p)
            if path:
                project.update(pid, exported_to=path)
                p = project.load(pid)
        except Exception as e:  # noqa: BLE001
            print(f"[export] gagal: {e}")
    send_webhook(p, event)


# ------------------------------------------------------------------ inbox
_seen: dict[Path, tuple[int, float]] = {}


def scan_inbox_once() -> list[str]:
    """Proses file video yang sudah selesai disalin (ukuran stabil) di inbox. Kembalikan id proyek baru."""
    cfg = _cfg()
    if not cfg.get("inbox_enabled"):
        return []
    from . import project

    created = []
    for f in sorted(INBOX_DIR.iterdir()):
        if not f.is_file() or f.suffix.lower() not in VIDEO_EXT:
            continue
        st = f.stat()
        prev = _seen.get(f)
        _seen[f] = (st.st_size, st.st_mtime)
        if prev != (st.st_size, st.st_mtime) or time.time() - st.st_mtime < 3:
            continue  # masih disalin
        dst = DONE_DIR / f.name
        n = 2
        while dst.exists():
            dst = DONE_DIR / f"{f.stem} ({n}){f.suffix}"
            n += 1
        shutil.move(str(f), dst)
        _seen.pop(f, None)
        tpl = project.list_templates().get(cfg.get("inbox_template") or "", {})
        p = project.create(str(dst), {**tpl, "origin": "inbox"})
        created.append(p["id"])
        print(f"[inbox] {f.name} → proyek {p['id']}")
    return created


def start_inbox_watcher(interval: float = 4.0) -> None:
    def loop():
        while True:
            try:
                scan_inbox_once()
            except Exception as e:  # noqa: BLE001
                print(f"[inbox] {e}")
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True, name="clipper-inbox").start()
