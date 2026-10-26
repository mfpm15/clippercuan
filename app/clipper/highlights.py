"""Cari momen menarik dari transkrip + energi audio, lalu buat judul pembuka.

Skor tiap kandidat (0..100) gabungan dari:
  hook      kalimat pembuka berisi pertanyaan / angka / kata pemicu
  keywords  kata emosional & pemicu penasaran di sepanjang klip
  energy    rata-rata + puncak energi audio
  pace      kecepatan bicara (kata per detik) — terlalu lambat = membosankan
  complete  klip berakhir di akhir kalimat
"""
from __future__ import annotations

import re

import numpy as np

HOOK_WORDS = {
    # Indonesia
    "rahasia", "jangan", "ternyata", "kenapa", "gimana", "bagaimana", "cara", "trik", "tips", "kesalahan",
    "penting", "wajib", "harus", "pertama", "terbesar", "terbaik", "terburuk", "jujur", "sebenarnya",
    "nggak", "gak", "enggak", "tidak", "pernah", "semua", "orang", "kamu", "lo", "lu", "gue", "aku",
    "uang", "duit", "cuan", "gaji", "juta", "miliar", "gratis", "bahaya", "gila", "parah", "serius",
    "kaget", "viral", "stop", "berhenti", "hidup", "mati", "sukses", "gagal", "bisnis", "rezeki",
    # English
    "secret", "never", "always", "why", "how", "mistake", "biggest", "best", "worst", "money", "truth",
    "actually", "crazy", "insane", "important", "stop", "you", "nobody", "everyone", "million", "free",
}
EMO_WORDS = {
    "wow", "anjir", "astaga", "gokil", "mantap", "keren", "sedih", "senang", "marah", "takut", "cinta",
    "benci", "bangga", "malu", "nangis", "ketawa", "lucu", "amazing", "love", "hate", "scared", "funny",
}
_TOKEN = re.compile(r"[\w']+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def _ends_sentence(text: str) -> bool:
    return text.rstrip().endswith((".", "?", "!", "…", "。", "？", "！"))


def _hook_score(text: str) -> float:
    toks = _tokens(text)[:18]
    s = 0.0
    if "?" in text:
        s += 0.35
    if any(t.isdigit() for t in toks):
        s += 0.2
    s += min(sum(t in HOOK_WORDS for t in toks) * 0.15, 0.6)
    return min(s, 1.0)


def score_candidates(tr: dict, energy: np.ndarray, min_sec: float = 20, max_sec: float = 60, hop: float = 0.5) -> list[dict]:
    """Semua jendela kandidat (dari batas kalimat) beserta skor lokal, urut terbaik."""
    segs, words = tr["segments"], tr["words"]
    cands = []
    for i, first in enumerate(segs):
        text_parts = []
        for j in range(i, len(segs)):
            text_parts.append(segs[j]["text"])
            start, end = first["s"], segs[j]["e"]
            length = end - start
            if length > max_sec:
                break
            if length < min_sec:
                continue
            full = " ".join(text_parts)
            toks = _tokens(full)
            nwords = sum(len(segs[k]["words"]) for k in range(i, j + 1))
            pace = nwords / max(length, 1)
            e0, e1 = int(start / hop), max(int(end / hop), int(start / hop) + 1)
            en = energy[e0:e1] if energy.size else np.zeros(1)
            if en.size == 0:
                en = np.zeros(1)
            energy_s = float(en.mean() * 0.6 + np.percentile(en, 90) * 0.4)
            kw = sum(t in HOOK_WORDS for t in toks) + 1.5 * sum(t in EMO_WORDS for t in toks)
            kw_s = min(kw / max(len(toks), 1) * 6, 1.0)
            pace_s = float(np.clip((pace - 1.2) / 2.0, 0, 1))
            complete = 1.0 if _ends_sentence(segs[j]["text"]) else 0.3
            conf = float(np.mean([words[k]["p"] for k in range(first["words"][0], segs[j]["words"][-1] + 1)]))
            ideal = 1 - min(abs(length - (min_sec + max_sec) / 2) / max_sec, 1) * 0.3
            score = (0.30 * _hook_score(first["text"]) + 0.20 * kw_s + 0.20 * energy_s + 0.15 * pace_s
                     + 0.10 * complete + 0.05 * conf) * ideal
            cands.append({"s": start, "e": end, "seg0": i, "seg1": j, "score": score, "text": full})
    if not cands and segs:  # video lebih pendek dari min_sec
        cands = [{"s": segs[0]["s"], "e": segs[-1]["e"], "seg0": 0, "seg1": len(segs) - 1, "score": 0.5,
                  "text": " ".join(x["text"] for x in segs)}]
    cands.sort(key=lambda c: c["score"], reverse=True)
    return cands


def non_overlapping(cands: list[dict], count: int, max_overlap: float = 0.15, taken: list[dict] | None = None) -> list[dict]:
    chosen = list(taken or [])
    for c in cands:
        if len(chosen) >= count:
            break
        if all(min(c["e"], o["e"]) - max(c["s"], o["s"]) < max_overlap * (c["e"] - c["s"]) for o in chosen):
            chosen.append(c)
    return chosen


def explain(c: dict, segs: list[dict]) -> str:
    """Alasan singkat (bahasa manusia) kenapa kandidat ini dipilih skor lokal."""
    first = segs[c["seg0"]]["text"]
    toks = _tokens(c["text"])
    why = []
    if "?" in first:
        why.append("dibuka dengan pertanyaan")
    elif any(t.isdigit() for t in _tokens(first)):
        why.append("dibuka dengan angka")
    elif _hook_score(first) >= 0.3:
        why.append("kalimat pembuka kuat")
    kw = sorted({t for t in toks if t in HOOK_WORDS and len(t) > 3}, key=toks.index)[:3]
    if kw:
        why.append("kata pemicu: " + ", ".join(kw))
    if any(t in EMO_WORDS for t in toks):
        why.append("ada emosi")
    if _ends_sentence(segs[c["seg1"]]["text"]):
        why.append("berakhir di kalimat utuh")
    return " · ".join(why) or "alur bicara padat"


STOP = set("""yang dan di ke dari ini itu untuk dengan pada adalah juga tidak bisa akan ada kita kami saya aku kamu
dia mereka atau tapi jadi karena kalau sudah belum lebih sangat banyak satu dua tiga seperti dalam oleh agar
supaya bahwa saja lagi ya nah oke apa siapa kapan mana mau harus nya pun kenapa mengapa gimana bagaimana
pertama kedua ketiga terakhir semua orang nggak enggak gak tidak pernah sekarang nanti tadi hari waktu cara
benar benar sebenarnya ternyata jangan coba sama setiap selalu masih bukan hanya bisa banget kalian
the a an and or of to in on for is are was were be it this that with as at by you your i we they he she not
but so if just very more why how what when never always""".split())


def post_kit(text: str, title: str, language: str | None = None) -> dict:
    """Caption posting + hashtag tanpa AI: kata kunci terbanyak + tag umum short video."""
    toks = [t for t in _tokens(text) if len(t) > 3 and t not in STOP and not t.isdigit()]
    freq: dict[str, int] = {}
    for t in toks:
        freq[t] = freq.get(t, 0) + 1 + (0.5 if len(t) > 6 else 0)  # kata panjang cenderung kata kunci topik
    keys = [k for k, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:5]]
    base = ["#fyp", "#reels", "#shorts"] if language != "id" else ["#fyp", "#reelsindonesia", "#shortsindonesia"]
    tags = [f"#{k}" for k in keys] + base
    cta = "Setuju nggak? Tulis pendapatmu di komentar 👇" if language in (None, "id", "ms") else "Agree? Tell me in the comments 👇"
    head = title.strip()
    if head and head[-1] not in ".?!…":
        head += "…"
    return {"caption": f"{head}\n\n{cta}".strip(), "hashtags": tags}


def to_moment(c: dict, segs: list[dict], duration: float, score: int, title: str | None = None, **extra) -> dict:
    extra.setdefault("reason", explain(c, segs))
    return {
        "start": round(max(c["s"] - 0.15, 0), 2), "end": round(min(c["e"] + 0.35, duration), 2), "score": int(score),
        "title": title or make_title([segs[k]["text"] for k in range(c["seg0"], c["seg1"] + 1)]),
        "text": c["text"], **extra,
    }


def find_moments(tr: dict, energy: np.ndarray, duration: float, count: int = 6,
                 min_sec: float = 20, max_sec: float = 60, hop: float = 0.5) -> list[dict]:
    if not tr["segments"]:
        return _fallback(duration, count, min_sec, max_sec)
    chosen = non_overlapping(score_candidates(tr, energy, min_sec, max_sec, hop), count)
    top = max(c["score"] for c in chosen) or 1
    out = [to_moment(c, tr["segments"], duration, round(60 + 39 * c["score"] / top)) for c in chosen]
    out.sort(key=lambda m: m["score"], reverse=True)
    return out


def _fallback(duration, count, min_sec, max_sec):
    """Tanpa ucapan (mis. gameplay tanpa suara): bagi rata."""
    length = min(max_sec, max(min_sec, duration / max(count, 1)))
    out, t = [], 0.0
    while t + min_sec <= duration and len(out) < count:
        out.append({"start": round(t, 2), "end": round(min(t + length, duration), 2), "score": 60, "title": f"Momen {len(out) + 1}", "text": ""})
        t += length
    return out or [{"start": 0, "end": round(duration, 2), "score": 60, "title": "Momen 1", "text": ""}]


def make_title(sentences: list[str], max_words: int = 7) -> str:
    """Pilih kalimat paling 'menjual' lalu ringkas jadi judul pembuka."""
    best, best_s = sentences[0] if sentences else "", -1.0
    for i, s in enumerate(sentences[:6]):
        sc = _hook_score(s) + (0.15 if i == 0 else 0) - max(len(_tokens(s)) - 14, 0) * 0.02
        if sc > best_s:
            best, best_s = s, sc
    best = re.sub(r"^(jadi|nah|oke|ok|terus|dan|ya|so|and|well|um|eh)[,\s]+", "", best.strip(), flags=re.I)
    words = best.split()
    title = " ".join(words[:max_words]).strip(" ,.;:")
    if len(words) > max_words and not title.endswith("?"):
        title += "…"
    return title[:1].upper() + title[1:] if title else "Momen terbaik"
