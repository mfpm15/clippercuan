"""Klien LLM untuk router kompatibel OpenAI (9router, OpenRouter, LiteLLM, dsb).

Dipakai untuk:
  - memilih momen paling viral dari kandidat transkrip  (model "moments")
  - membuat judul hook pembuka                          (model "titles")
  - membuat caption posting + hashtag                   (model "titles")
Jika LLM mati / gagal, aplikasi otomatis kembali ke skor lokal.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from .config import DATA_DIR

SETTINGS_FILE = DATA_DIR / "settings.json"
DEFAULT_LLM = {
    "enabled": False,
    "base_url": "http://localhost:20128/v1",   # alamat default 9router; ubah di Pengaturan
    "api_key": "",
    "model_moments": "",                        # mis. claude-sonnet / gpt thinker
    "model_titles": "",                         # mis. haiku / gemini flash (cepat & murah)
    "temperature": 0.4,
    "timeout": 180,
}


# ------------------------------------------------------------------ settings
DEFAULT_AUTOMATION = {
    "webhook_url": "",          # POST JSON saat proyek selesai/gagal (untuk AI agent / n8n / Zapier)
    "inbox_enabled": False,     # proses otomatis video yang ditaruh di folder inbox
    "inbox_template": "",       # nama template gaya untuk inbox ("" = pengaturan bawaan)
    "export_dir": "",           # salin hasil klip otomatis ke folder ini
}


def load_settings() -> dict:
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text("utf-8"))
        except Exception:
            data = {}
    return {"llm": {**DEFAULT_LLM, **data.get("llm", {})},
            "automation": {**DEFAULT_AUTOMATION, **data.get("automation", {})}}


def save_settings(new: dict) -> dict:
    cur = load_settings()
    if "llm" in new:
        llm = {k: v for k, v in new["llm"].items() if k in DEFAULT_LLM}
        if llm.get("api_key") == "••••":   # UI mengirim mask = tidak diubah
            llm.pop("api_key")
        cur["llm"].update(llm)
        cur["llm"]["base_url"] = cur["llm"]["base_url"].strip().rstrip("/")
    if "automation" in new:
        cur["automation"].update({k: v for k, v in new["automation"].items() if k in DEFAULT_AUTOMATION})
    SETTINGS_FILE.write_text(json.dumps(cur, indent=1), "utf-8")
    return cur


def public_settings() -> dict:
    s = load_settings()
    s["llm"]["api_key"] = "••••" if s["llm"]["api_key"] else ""
    return s


def cfg() -> dict:
    return load_settings()["llm"]


def active(task: str = "moments") -> bool:
    c = cfg()
    return bool(c["enabled"] and c["base_url"] and c.get(f"model_{task}"))


# ------------------------------------------------------------------ transport
class LLMError(RuntimeError):
    pass


def _req(path: str, body: dict | None = None, c: dict | None = None, timeout: float | None = None) -> dict:
    c = c or cfg()
    url = c["base_url"].rstrip("/") + path
    headers = {"Content-Type": "application/json", "User-Agent": "ClipperCuan/1.0"}
    if c.get("api_key"):
        headers["Authorization"] = "Bearer " + c["api_key"]
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout or c.get("timeout", 180)) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise LLMError(f"HTTP {e.code} dari {url}: {detail}") from None
    except urllib.error.URLError as e:
        raise LLMError(f"Tidak bisa terhubung ke {url} ({e.reason}). Pastikan 9router berjalan.") from None
    except json.JSONDecodeError:
        raise LLMError(f"Respons bukan JSON dari {url}") from None


def list_models(c: dict | None = None) -> list[str]:
    data = _req("/models", c=c, timeout=20)
    items = data.get("data", data if isinstance(data, list) else [])
    return sorted({m.get("id") if isinstance(m, dict) else str(m) for m in items} - {None})


def chat(model: str, system: str, user: str, c: dict | None = None, max_tokens: int = 4000) -> str:
    c = c or cfg()
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": float(c.get("temperature", 0.4)),
        "max_tokens": max_tokens,
    }
    data = _req("/chat/completions", body, c=c)
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"Format respons tak dikenal: {str(data)[:300]}")
    content = msg.get("content")
    if isinstance(content, list):  # beberapa router mengirim potongan konten
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    if not content:
        raise LLMError("Model mengembalikan jawaban kosong (coba naikkan batas token atau ganti model).")
    return content


def _json(text: str):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise LLMError("Model tidak mengembalikan JSON")
    for end in range(len(text), start, -1):
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            continue
    raise LLMError("JSON dari model tidak valid")


# ------------------------------------------------------------------ tugas
SYS_EDITOR = (
    "Kamu editor video pendek profesional untuk TikTok, Reels, dan Shorts. Tugasmu memilih potongan "
    "yang punya hook kuat di 3 detik pertama, berdiri sendiri tanpa konteks, punya emosi/insight/kejutan, "
    "dan berakhir di titik yang memuaskan. Jawab HANYA dengan JSON valid."
)


def pick_moments(cands: list[dict], count: int, language: str | None) -> list[dict]:
    """cands: [{id, start, end, text}] → [{id, score, title, reason, hashtags}] urut terbaik."""
    c = cfg()
    lines = [f'#{x["id"]} [{x["start"]:.0f}s–{x["end"]:.0f}s, {x["end"] - x["start"]:.0f}dtk]: {x["text"][:900]}' for x in cands]
    user = (
        f"Bahasa video: {language or 'tidak diketahui'}. Pilih {count} kandidat TERBAIK yang tidak saling tumpang tindih "
        f"dari daftar berikut.\n\n" + "\n\n".join(lines) +
        "\n\nUntuk tiap pilihan buat judul pembuka maksimal 8 kata dalam bahasa yang sama dengan video, "
        "memancing rasa penasaran (bukan clickbait palsu).\n"
        'Format: {"clips":[{"id":<nomor>,"score":<0-100>,"title":"...","reason":"alasan singkat","hashtags":["#a","#b","#c"]}]}'
    )
    out = _json(chat(c["model_moments"], SYS_EDITOR, user, c))
    clips = out.get("clips", out) if isinstance(out, dict) else out
    res = []
    for x in clips if isinstance(clips, list) else []:
        try:
            res.append({"id": int(str(x["id"]).lstrip("#")), "score": int(x.get("score", 80)), "title": str(x.get("title", "")).strip(),
                        "reason": str(x.get("reason", "")), "hashtags": [str(h) for h in x.get("hashtags", [])][:8]})
        except (KeyError, ValueError, TypeError):
            continue
    if not res:
        raise LLMError("Model tidak memilih klip apa pun")
    return res


def make_title(text: str, language: str | None, style: str = "penasaran") -> list[str]:
    c = cfg()
    model = c["model_titles"] or c["model_moments"]
    user = (f"Transkrip klip:\n{text[:2500]}\n\nBuat 5 alternatif judul pembuka ({style}), maksimal 8 kata, "
            f"bahasa sama dengan transkrip ({language or 'auto'}). Format: {{\"titles\":[\"...\"]}}")
    out = _json(chat(model, SYS_EDITOR, user, c, max_tokens=1500))
    titles = out.get("titles", []) if isinstance(out, dict) else out
    return [str(t).strip() for t in titles if str(t).strip()][:5]


def make_post(text: str, title: str, language: str | None) -> dict:
    c = cfg()
    model = c["model_titles"] or c["model_moments"]
    user = (f"Judul klip: {title}\nTranskrip:\n{text[:2500]}\n\nTulis caption posting singkat (maks 2 kalimat + ajakan "
            f"interaksi) dan 6-10 hashtag relevan, bahasa {language or 'sama dengan transkrip'}. "
            'Format: {"caption":"...","hashtags":["#..."]}')
    out = _json(chat(model, SYS_EDITOR, user, c, max_tokens=1500))
    return {"caption": str(out.get("caption", "")), "hashtags": [str(h) for h in out.get("hashtags", [])][:12]}
