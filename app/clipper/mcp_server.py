"""Server MCP (stdio) — supaya AI agent (Claude Code/Desktop, Cursor, agent buatan sendiri) bisa
menjalankan ClipperCuan secara otomatis.

Jalankan:  python -m clipper mcp
Agent memanggil tools di bawah; server MCP ini meneruskan ke server lokal ClipperCuan
(http://127.0.0.1:8765) dan menyalakannya otomatis bila belum berjalan, sehingga
proyek yang dibuat agent juga tampil di UI.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

BASE = os.environ.get("CLIPPER_URL", "http://127.0.0.1:8765").rstrip("/")   # bisa server cloud
TOKEN = os.environ.get("CLIPPER_TOKEN", "").strip()
mcp = FastMCP("clippercuan")


# ------------------------------------------------------------------ http helper
def _call(method: str, path: str, body: dict | None = None, timeout: float = 60):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8")).get("detail")
        except Exception:  # noqa: BLE001
            detail = str(e)
        raise RuntimeError(f"ClipperCuan menolak permintaan ({e.code}): {detail}") from None


def _alive() -> bool:
    try:
        _call("GET", "/api/info", timeout=3)
        return True
    except RuntimeError as e:
        if "(401)" in str(e):  # server hidup tapi password salah — jangan coba menyalakan server baru
            raise RuntimeError("Password ClipperCuan salah/kosong: periksa CLIPPER_TOKEN di konfigurasi MCP.") from None
        return False
    except Exception:  # noqa: BLE001
        return False


def _ensure_server() -> None:
    if _alive():
        return
    u = urllib.parse.urlparse(BASE)
    if u.hostname not in ("127.0.0.1", "localhost"):
        raise RuntimeError(f"Server ClipperCuan di {BASE} tidak bisa dihubungi (cek alamat & CLIPPER_TOKEN).")
    port = u.port or 8765
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    cmd = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "clipper"]
    subprocess.Popen(cmd + ["--no-browser", "--strict-port", "--port", str(port)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                     cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     creationflags=flags, start_new_session=not sys.platform.startswith("win"))
    for _ in range(60):
        time.sleep(0.5)
        if _alive():
            return
    raise RuntimeError("Server ClipperCuan tidak bisa dinyalakan. Jalankan start.bat / start.command dulu.")


def _summary(pid: str) -> dict:
    return _call("GET", f"/api/projects/{pid}/summary")


def _wait(pid: str, timeout_sec: int) -> dict:
    end = time.time() + timeout_sec
    while True:
        s = _summary(pid)
        busy = s["status"] in ("queued", "running") or any(c["status"] in ("queued", "rendering") for c in s["clips"])
        if not busy or time.time() > end:
            s["timed_out"] = busy
            return s
        time.sleep(3)


# ------------------------------------------------------------------ tools
@mcp.tool()
def create_clips(source: str, clip_count: int = 6, layout: str = "portrait", template: str = "",
                 language: str = "auto", min_sec: int = 20, max_sec: int = 60, caption_style: str = "",
                 cut_silence: bool | None = None, emoji: bool | None = None, transcriber: str = "",
                 extra_settings: dict | None = None,
                 wait: bool = False, timeout_sec: int = 3600) -> dict:
    """Buat klip vertikal dari video panjang.

    source: link (YouTube/TikTok/IG/…) atau path file video lokal di komputer ini.
    layout: portrait | square | blur | split | landscape.
    template: nama template gaya yang tersimpan (lihat list_templates); pengaturan lain menimpanya.
    caption_style: box | wbw | karaoke | clean (kosong = ikut template/bawaan).
    transcriber: auto | youtube | api | local — sumber subtitle (auto: YouTube → API cloud → Whisper lokal).
    extra_settings: pengaturan lanjutan (mis. {"title": {"preset": "neon"}, "music": {"enabled": true, "file": "..."}}).
    wait: true = tunggu sampai semua klip selesai lalu kembalikan hasil (path file video, caption, hashtag).
    """
    _ensure_server()
    settings: dict = {}
    if template:
        tpls = _call("GET", "/api/templates")
        if template not in tpls:
            raise RuntimeError(f"Template '{template}' tidak ada. Tersedia: {', '.join(tpls) or '(kosong)'}")
        settings.update(tpls[template])
    settings.update({"clip_count": clip_count, "layout": layout, "language": language, "min_sec": min_sec, "max_sec": max_sec})
    if caption_style:
        settings.setdefault("caption", {})["style"] = caption_style
    if cut_silence is not None:
        settings["cut_silence"] = cut_silence
    if transcriber:
        settings["transcriber"] = transcriber
    if emoji is not None:
        settings.setdefault("emoji", {})["enabled"] = emoji
    for k, v in (extra_settings or {}).items():
        settings[k] = {**settings.get(k, {}), **v} if isinstance(v, dict) and isinstance(settings.get(k), dict) else v
    p = _call("POST", "/api/projects", {"source": source, "settings": settings})
    return _wait(p["id"], timeout_sec) if wait else _summary(p["id"])


@mcp.tool()
def get_project(project_id: str) -> dict:
    """Status & hasil proyek: progres, daftar klip (path video, SRT, judul, caption, hashtag, skor)."""
    _ensure_server()
    return _summary(project_id)


@mcp.tool()
def wait_for_project(project_id: str, timeout_sec: int = 3600) -> dict:
    """Tunggu sampai proyek (dan semua render ulang) selesai, lalu kembalikan hasilnya."""
    _ensure_server()
    return _wait(project_id, timeout_sec)


@mcp.tool()
def list_projects(limit: int = 20) -> list:
    """Daftar proyek terbaru (id, judul, status, jumlah klip)."""
    _ensure_server()
    return _call("GET", "/api/projects")[:limit]


@mcp.tool()
def edit_clip(project_id: str, clip_id: str, title: str | None = None, start: float | None = None,
              end: float | None = None, layout: str | None = None, caption: str | None = None,
              hashtags: list[str] | None = None) -> dict:
    """Ubah satu klip lalu render ulang: judul, potongan (detik di video sumber), format, atau teks posting."""
    _ensure_server()
    changes: dict = {}
    if title is not None:
        changes["title"] = title
    if start is not None:
        changes["start"] = start
    if end is not None:
        changes["end"] = end
    if layout:
        changes["overrides"] = {"layout": layout}
    rerender = bool(changes)
    if caption is not None or hashtags is not None:
        cur = next((c for c in _summary(project_id)["clips"] if c["id"] == clip_id), None)
        if cur is None:
            raise RuntimeError(f"Klip {clip_id} tidak ditemukan")
        changes["post"] = {"caption": caption if caption is not None else cur["caption"],
                           "hashtags": hashtags if hashtags is not None else cur["hashtags"]}
    if not changes:
        raise RuntimeError("Tidak ada perubahan")
    _call("PATCH", f"/api/projects/{project_id}/clips/{clip_id}", {"changes": changes, "rerender": rerender})
    return _summary(project_id)


@mcp.tool()
def add_clip(project_id: str, start: float, end: float, title: str = "") -> dict:
    """Tambah klip manual dari rentang waktu (detik) video sumber."""
    _ensure_server()
    _call("POST", f"/api/projects/{project_id}/clips", {"start": start, "end": end, "title": title})
    return _summary(project_id)


@mcp.tool()
def delete_clip(project_id: str, clip_id: str) -> dict:
    """Hapus satu klip dari proyek."""
    _ensure_server()
    _call("DELETE", f"/api/projects/{project_id}/clips/{clip_id}")
    return _summary(project_id)


@mcp.tool()
def restyle_project(project_id: str, settings: dict) -> dict:
    """Render ulang semua klip dengan gaya baru, mis. {"layout":"blur","caption":{"style":"wbw"},"emoji":{"enabled":true}}."""
    _ensure_server()
    _call("POST", f"/api/projects/{project_id}/rerender", {"settings": settings})
    return _summary(project_id)


@mcp.tool()
def export_project(project_id: str, folder: str = "") -> dict:
    """Ekspor semua klip selesai (MP4 + SRT + caption-posting.txt). folder kosong = ZIP di folder proyek."""
    _ensure_server()
    return _call("POST", f"/api/projects/{project_id}/export", {"folder": folder})


@mcp.tool()
def list_templates() -> dict:
    """Template gaya yang tersimpan (nama → pengaturan)."""
    _ensure_server()
    return _call("GET", "/api/templates")


@mcp.tool()
def system_check() -> dict:
    """Cek kesiapan sistem: FFmpeg/libass, GPU, model Whisper, ruang disk."""
    _ensure_server()
    return _call("GET", "/api/system")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
