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
    from . import project

    settings = {"clip_count": args.clips, "layout": args.layout, "language": args.lang, "model": args.model,
                "min_sec": args.min, "max_sec": args.max}
    if args.caption:
        settings["caption"] = {"style": args.caption}
    project.start_worker()  # sebelum create: pemulihan job terputus tidak boleh menyentuh proyek baru
    p = project.create(args.source, settings)
    last = ""
    while True:
        p = project.load(p["id"])
        line = f"[{p['progress'] * 100:5.1f}%] {p['message']}"
        if line != last:
            print(line, flush=True)
            last = line
        if p["status"] in ("done", "error", "cancelled"):
            break
        time.sleep(0.5)
    if p["status"] != "done":
        print(p.get("error") or p["message"], file=sys.stderr)
        sys.exit(1)
    print(json.dumps([{k: c.get(k) for k in ("id", "score", "start", "end", "title", "file", "status")} for c in p["clips"]], indent=1, ensure_ascii=False))
    print("Folder hasil:", project.pdir(p["id"]))


def main() -> None:
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
    a = ap.parse_args()
    if a.cmd == "cli":
        cli(a)
    else:
        serve(a.port, not a.no_browser)


if __name__ == "__main__":
    main()
