"""Jalankan: python -m clipper  (UI di browser)  |  python -m clipper cli <link/file> (tanpa UI)."""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
import webbrowser


def _free_port(preferred: int) -> int:
    for port in (preferred, *range(preferred + 1, preferred + 20)):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


def serve(port: int, open_browser: bool) -> None:
    import uvicorn

    port = _free_port(port)
    url = f"http://127.0.0.1:{port}"
    print(f"\n  ClipperCuan berjalan di {url}\n  Biarkan jendela ini terbuka. Tutup untuk keluar.\n")
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run("clipper.server:app", host="127.0.0.1", port=port, log_level="warning")


def cli(args) -> None:
    from . import automation, project

    settings: dict = {}
    if args.template:
        tpl = project.list_templates()
        if args.template not in tpl:
            sys.exit(f"Template '{args.template}' tidak ada. Tersedia: {', '.join(tpl) or '(kosong)'}")
        settings.update(tpl[args.template])
    settings.update({"clip_count": args.clips, "layout": args.layout, "language": args.lang, "model": args.model,
                     "min_sec": args.min, "max_sec": args.max})
    if args.caption:
        settings.setdefault("caption", {})["style"] = args.caption
    if args.cut_silence:
        settings["cut_silence"] = True
    if args.emoji:
        settings.setdefault("emoji", {})["enabled"] = True
    if args.export:
        settings["export_dir"] = args.export
    if args.settings:
        settings.update(json.loads(args.settings))
    log = (lambda *a: print(*a, file=sys.stderr, flush=True)) if args.json else (lambda *a: print(*a, flush=True))
    project.start_worker()  # sebelum create: pemulihan job terputus tidak boleh menyentuh proyek baru
    p = project.create(args.source, settings)
    last = ""
    while True:
        p = project.load(p["id"])
        line = f"[{p['progress'] * 100:5.1f}%] {p['message']}"
        if line != last:
            log(line)
            last = line
        if p["status"] in ("done", "error", "cancelled"):
            break
        time.sleep(0.5)
    time.sleep(0.5)  # beri waktu ekspor otomatis/webhook
    p = project.load(p["id"])
    if args.json:
        print(json.dumps(automation.summary(p), indent=1, ensure_ascii=False))
    else:
        for c in automation.summary(p)["clips"]:
            print(f"  ★{c['score']:>3}  {c['title']}\n        {c['video_path']}")
        print("Folder hasil:", project.pdir(p["id"]), ("\nDiekspor ke: " + p["exported_to"]) if p.get("exported_to") else "")
    if p["status"] != "done":
        log(p.get("error") or p["message"])
        sys.exit(1)


def _utf8_console() -> None:
    """Konsol Windows lama (cp1252/cp437) tidak bisa mencetak emoji/aksara non-Latin → paksa UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main() -> None:
    _utf8_console()
    ap = argparse.ArgumentParser(prog="clipper", description="ClipperCuan — AI clipper lokal")
    sub = ap.add_subparsers(dest="cmd")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    c = sub.add_parser("cli", help="proses tanpa UI")
    c.add_argument("source", help="link video atau path file")
    c.add_argument("--clips", type=int, default=6)
    c.add_argument("--layout", default="portrait", choices=["portrait", "square", "blur", "split", "landscape"])
    c.add_argument("--lang", default="auto")
    c.add_argument("--model", default="small")
    c.add_argument("--caption", choices=["box", "wbw", "karaoke", "clean"])
    c.add_argument("--min", type=float, default=20)
    c.add_argument("--max", type=float, default=60)
    c.add_argument("--template", help="nama template gaya yang tersimpan")
    c.add_argument("--cut-silence", action="store_true", help="potong jeda hening")
    c.add_argument("--emoji", action="store_true", help="emoji otomatis")
    c.add_argument("--export", help="salin hasil ke folder ini")
    c.add_argument("--settings", help='JSON pengaturan tambahan, mis. \'{"title":{"preset":"neon"}}\'')
    c.add_argument("--json", action="store_true", help="cetak hasil sebagai JSON (untuk agent/skrip)")
    sub.add_parser("mcp", help="jalankan server MCP (stdio) untuk AI agent")
    a = ap.parse_args()
    if a.cmd == "cli":
        cli(a)
    elif a.cmd == "mcp":
        from .mcp_server import main as mcp_main

        mcp_main()
    else:
        serve(a.port, not a.no_browser)


if __name__ == "__main__":
    main()
