"""Sumber transkripsi selain Whisper lokal — supaya komputer tidak perlu bekerja berat:

  youtube : subtitle bawaan YouTube (manual atau otomatis) → tanpa komputasi sama sekali
  api     : layanan speech-to-text kompatibel OpenAI (Groq, OpenAI, 9router, LocalAI, …)

Semua menghasilkan format yang sama dengan transcribe.transcribe():
  {"language": "id", "words": [{"w","s","e","p"}], "segments": [{"text","s","e","words":[idx..]}], "source": "..."}
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Callable

from .config import FFMPEG
from .media import _NO_WINDOW

_SENT_END = (".", "?", "!", "…", "。", "？", "！")


# ------------------------------------------------------------------ util bersama
def build_segments(words: list[dict], max_words: int = 18, gap: float = 0.8) -> list[dict]:
    """Kelompokkan kata jadi 'kalimat' (tanda baca, jeda panjang, atau batas panjang)."""
    segs, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        nxt_gap = words[i + 1]["s"] - w["e"] if i + 1 < len(words) else 99
        if w["w"].endswith(_SENT_END) or nxt_gap > gap or len(cur) >= max_words:
            segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)
    return [{"text": " ".join(words[k]["w"] for k in idx), "s": words[idx[0]]["s"], "e": words[idx[-1]]["e"], "words": idx}
            for idx in segs]


def words_from_line(text: str, start: float, end: float) -> list[dict]:
    """Bagi durasi baris ke tiap kata sebanding panjang hurufnya (untuk subtitle tanpa timing per kata)."""
    toks = text.split()
    if not toks:
        return []
    total = sum(len(t) + 1 for t in toks)
    out, t = [], start
    for tok in toks:
        d = (end - start) * (len(tok) + 1) / total
        out.append({"w": tok, "s": round(t, 3), "e": round(t + d * 0.92, 3), "p": 0.8})
        t += d
    return out


def _finish(words: list[dict], language: str | None, source: str) -> dict:
    words = [w for w in words if w["w"].strip()]
    words.sort(key=lambda w: w["s"])
    for a, b in zip(words, words[1:]):  # rapikan tumpang tindih
        if a["e"] > b["s"]:
            a["e"] = max(a["s"] + 0.05, b["s"])
    return {"language": language, "words": words, "segments": build_segments(words), "source": source}


# ------------------------------------------------------------------ YouTube
_YT = re.compile(r"(^|\.)(youtube\.com|youtu\.be)$", re.I)


def is_youtube(url: str) -> bool:
    try:
        from urllib.parse import urlparse

        return bool(_YT.search(urlparse(url.strip()).hostname or ""))
    except Exception:  # noqa: BLE001
        return False


def parse_json3(data: dict) -> list[dict]:
    """json3 YouTube → kata. Subtitle otomatis punya timing per kata (tOffsetMs); manual hanya per baris."""
    words: list[dict] = []
    events = [e for e in data.get("events", []) if e.get("segs")]
    for i, ev in enumerate(events):
        t0 = ev.get("tStartMs", 0) / 1000
        dur = ev.get("dDurationMs", 0) / 1000
        segs = [s for s in ev["segs"] if s.get("utf8", "").strip()]
        if not segs:
            continue
        nxt = events[i + 1].get("tStartMs", 0) / 1000 if i + 1 < len(events) else t0 + dur
        if len(segs) > 1 or "tOffsetMs" in segs[0]:  # timing per kata
            for k, s in enumerate(segs):
                st = t0 + s.get("tOffsetMs", 0) / 1000
                en = t0 + segs[k + 1].get("tOffsetMs", 0) / 1000 if k + 1 < len(segs) else min(t0 + dur, nxt)
                for j, part in enumerate(s["utf8"].split()):  # satu seg bisa berisi >1 kata
                    words.append({"w": part, "s": round(st, 3), "e": round(max(en, st + 0.1), 3), "p": 0.85})
        else:
            words += words_from_line(segs[0]["utf8"].replace("\n", " "), t0, t0 + dur)
    return words


def youtube_captions(url: str, language: str = "auto", log: Callable[[str], None] = print) -> dict | None:
    """Ambil subtitle YouTube (manual diutamakan, lalu otomatis). None bila tidak tersedia."""
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}) as ydl:
        info = ydl.extract_info(url, download=False)
        manual, auto = info.get("subtitles") or {}, info.get("automatic_captions") or {}
        orig = info.get("language") or next((k[:-5] for k in auto if k.endswith("-orig")), None)
        want = None if language in ("", "auto", None) else language
        # urutan pilihan: bahasa yang diminta / bahasa asli video, manual dulu baru otomatis
        cands = []
        for lang in [want, orig] if want else [orig]:
            if not lang:
                continue
            for pool, kind in ((manual, "manual"), (auto, "auto")):
                for key in (lang, f"{lang}-orig"):
                    if key in pool:
                        cands.append((pool[key], kind, lang))
        if not cands and not want:  # bahasa asli tidak diketahui: subtitle manual apa pun
            cands = [(v, "manual", k) for k, v in manual.items() if k != "live_chat"][:1]
        for fmts, kind, lang in cands:
            f = next((x for x in fmts if x.get("ext") == "json3"), None)
            if not f:
                continue
            try:
                data = json.loads(ydl.urlopen(f["url"]).read().decode("utf-8"))
            except Exception as e:  # noqa: BLE001 — mis. HTTP 429
                log(f"[subtitle YouTube] {lang}/{kind} gagal: {e}")
                continue
            words = parse_json3(data)
            if len(words) >= 5:
                return _finish(words, lang, f"youtube-{kind}")
    return None


# ------------------------------------------------------------------ API speech-to-text (format OpenAI)
def _multipart(fields: dict, file_field: str, path: Path) -> tuple[bytes, str]:
    b = uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        for val in v if isinstance(v, list) else [v]:
            out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{val}\r\n'.encode()
    out += (f'--{b}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{path.name}"\r\n'
            f"Content-Type: audio/ogg\r\n\r\n").encode() + path.read_bytes() + b"\r\n"
    out += f"--{b}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={b}"


def _api_chunk(path: Path, cfg: dict, language: str | None, translate: bool) -> dict:
    url = cfg["base_url"].rstrip("/") + ("/audio/translations" if translate else "/audio/transcriptions")
    fields = {"model": cfg["model"], "response_format": "verbose_json",
              "timestamp_granularities[]": ["word", "segment"]}
    if language and not translate:
        fields["language"] = language
    body, ctype = _multipart(fields, "file", path)
    headers = {"Content-Type": ctype, "User-Agent": "ClipperCuan"}
    if cfg.get("api_key"):
        headers["Authorization"] = "Bearer " + cfg["api_key"]
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=float(cfg.get("timeout", 600))) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API transkripsi HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"API transkripsi tidak bisa dihubungi ({e.reason})") from None


def api_transcribe(wav: Path, cfg: dict, language: str = "auto", translate_en: bool = False,
                   duration: float | None = None, progress: Callable[[float, str], None] = lambda p, m: None,
                   chunk_sec: int = 600) -> dict:
    """Kirim audio (dikompres Opus mono 24 kbps, dipotong per 10 menit) ke API kompatibel OpenAI."""
    lang = None if language in ("", "auto", None) else language
    total = duration or 1
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-ar", "16000",
                        "-c:a", "libopus", "-b:a", "24k", "-f", "segment", "-segment_time", str(chunk_sec),
                        "-reset_timestamps", "1", str(tdp / "part%03d.ogg")], check=True, creationflags=_NO_WINDOW)
        parts = sorted(tdp.glob("part*.ogg"))
        words: list[dict] = []
        detected = lang
        for i, part in enumerate(parts):
            off = i * chunk_sec
            progress(i / max(len(parts), 1), f"Transkripsi cloud bagian {i + 1}/{len(parts)}…")
            res = _api_chunk(part, cfg, lang, translate_en)
            detected = detected or res.get("language")
            if res.get("words"):
                for w in res["words"]:
                    t = (w.get("word") or w.get("text") or "").strip()
                    if t:
                        words.append({"w": t, "s": round(off + float(w["start"]), 3), "e": round(off + float(w["end"]), 3), "p": 0.9})
            else:  # layanan tanpa timing per kata → bagi per segmen
                for sg in res.get("segments") or [{"text": res.get("text", ""), "start": 0, "end": min(chunk_sec, total - off)}]:
                    words += words_from_line(sg.get("text", ""), off + float(sg["start"]), off + float(sg["end"]))
        progress(1.0, "Transkripsi cloud selesai")
    names = {"indonesian": "id", "english": "en", "malay": "ms", "javanese": "jw", "sundanese": "su",
             "japanese": "ja", "korean": "ko", "chinese": "zh", "spanish": "es", "arabic": "ar", "hindi": "hi"}
    code = names.get((detected or "").lower(), detected)
    tr = _finish(words, code, "api")
    return tr


def test_api(cfg: dict) -> str:
    """Kirim 1 detik hening untuk memastikan endpoint & model benar."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "tes.ogg"
        subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                        "-t", "1", "-c:a", "libopus", "-b:a", "24k", str(p)], check=True, creationflags=_NO_WINDOW)
        res = _api_chunk(p, cfg, None, False)
    return "ok" if isinstance(res, dict) else str(res)[:200]
