"""Generator subtitle ASS: caption per kata (box/word-by-word/karaoke/clean), judul, watermark teks."""
from __future__ import annotations

FONT_PRESETS = {
    # nama tampilan → (nama font, bold)
    "Montserrat ExtraBold": ("Montserrat ExtraBold", 0),
    "Anton": ("Anton", 0),
    "Bebas Neue": ("Bebas Neue", 0),
    "Poppins Black": ("Poppins Black", 0),
    "Bangers": ("Bangers", 0),
    "Arial Black": ("Arial Black", 0),
    "Impact": ("Impact", 0),
    "Georgia Italic": ("Georgia", 1),
}


def _ass_color(hex_color: str, alpha: float = 1.0) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    a = f"{int(round((1 - alpha) * 255)):02X}"
    return f"&H{a}{b}{g}{r}".upper()


def _ts(t: float) -> str:
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def _word_tags(w: dict) -> str:
    """Gaya per kata dari editor: {"color": "#hex", "scale": 1.3}."""
    st = w.get("style") or {}
    tags = ""
    if st.get("color"):
        tags += r"\c" + _ass_color(st["color"])
    sc = st.get("scale")
    if sc and abs(float(sc) - 1) > 0.01:
        v = int(float(sc) * 100)
        tags += rf"\fscx{v}\fscy{v}"
    return tags


def chunk_words(words: list[dict], per_line: int) -> list[list[dict]]:
    """Kelompokkan kata jadi baris pendek; potong juga di jeda panjang atau tanda baca."""
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        gap = words[i + 1]["s"] - w["e"] if i + 1 < len(words) else 9
        if len(cur) >= per_line or gap > 0.6 or w["w"].endswith((".", "?", "!", ",")) or sum(len(x["w"]) for x in cur) > 18:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(words: list[dict], title: str, cfg: dict, size: tuple[int, int], duration: float) -> str:
    W, H = size
    cap, ttl, wm = cfg["caption"], cfg["title"], cfg["watermark"]
    font, italic = FONT_PRESETS.get(cap["font"], (cap["font"], 0))
    scale = W / 1080
    fs = int(cap["size"] * scale)
    align = {"bottom": 2, "middle": 5, "top": 8}[cap.get("position", "bottom")]
    margin_v = int(H * (0.22 if align == 2 else 0.12 if align == 8 else 0))
    white, hl = _ass_color(cap["color"]), _ass_color(cap["highlight"])
    tfs = int(ttl["size"] * scale)

    styles = [
        f"Style: Cap,{font},{fs},{white},{white},&H00000000,&H64000000,0,{italic},0,0,100,100,0,0,1,{max(int(5 * scale), 2)},{int(2 * scale)},{align},60,60,{margin_v},1",
        f"Style: CapBox,{font},{fs},&HFF000000,&HFF000000,{hl},&HFF000000,0,{italic},0,0,100,100,0,0,3,{max(int(10 * scale), 4)},0,{align},60,60,{margin_v},1",
        f"Style: TitleBar,{font},{tfs},&H00000000,&H00000000,{hl},&H00000000,0,0,0,0,100,100,0,0,3,{int(18 * scale)},0,8,90,90,{int(H * 0.10)},1",
        f"Style: TitleOutline,{font},{tfs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,{max(int(9 * scale), 4)},{max(int(4 * scale), 2)},8,90,90,{int(H * 0.10)},1",
        f"Style: TitleNeon,{font},{tfs},&H00FFFFFF,&H00FFFFFF,&H00FF7B8B,&H00FF7B8B,0,0,0,0,100,100,0,0,1,{max(int(4 * scale), 2)},0,8,90,90,{int(H * 0.10)},1",
        f"Style: TitleClean,{font},{tfs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,{max(int(3 * scale), 2)},{int(4 * scale)},8,90,90,{int(H * 0.10)},1",
        f"Style: Mark,Arial Black,{int(wm['size'] * scale)},{_ass_color('#FFFFFF', wm['opacity'])},&H00FFFFFF,{_ass_color('#000000', wm['opacity'] * 0.6)},&H00000000,0,0,0,0,100,100,0,0,1,{max(int(2 * scale), 1)},0,2,40,40,40,1",
    ]
    ev: list[str] = []

    def add(layer, start, end, style, text):
        if end > start:
            ev.append(f"Dialogue: {layer},{_ts(start)},{_ts(end)},{style},,0,0,0,,{text}")

    # ---- caption
    if cap["enabled"] and words:
        style = cap["style"]
        up = (lambda s: s.upper()) if cap.get("uppercase") else (lambda s: s)
        pop = cap.get("animation") == "pop"
        if style == "wbw":
            for i, w in enumerate(words):
                end = words[i + 1]["s"] if i + 1 < len(words) and words[i + 1]["s"] - w["e"] < 0.4 else w["e"]
                if i + 1 < len(words):
                    end = min(end, words[i + 1]["s"])
                anim = r"{\fscx70\fscy70\t(0,90,\fscx112\fscy112)\t(90,180,\fscx100\fscy100)}" if pop else ""
                add(1, w["s"], end, "Cap", anim + r"{\c" + hl + "}" + _esc(up(w["w"])))
        else:
            lines = chunk_words(words, int(cap.get("words_per_line", 3)))
            for li, line in enumerate(lines):
                l_end = line[-1]["e"] + 0.15
                if li + 1 < len(lines):  # jangan sampai bertumpuk dengan baris berikutnya
                    l_end = min(l_end, lines[li + 1][0]["s"])
                if style == "clean":
                    add(1, line[0]["s"], l_end, "Cap", _esc(up(" ".join(w["w"] for w in line))))
                    continue
                for k, w in enumerate(line):
                    s = w["s"] if k else line[0]["s"]
                    e = line[k + 1]["s"] if k + 1 < len(line) else l_end
                    grow = r"\t(0,80,\fscx108\fscy108)\t(80,160,\fscx100\fscy100)" if pop else ""
                    text_parts, box_parts = [], []
                    for j, x in enumerate(line):
                        t = _esc(up(x["w"]))
                        own = _word_tags(x)
                        if j == k:
                            col = "&H00000000&" if style == "box" else hl
                            text_parts.append("{" + own + r"\c" + col + (r"\bord0\shad0" if style == "box" else "") + grow + "}" + t + r"{\r}")
                            box_parts.append("{" + own + r"\1a&HFF&\3a&H00&\4a&HFF&" + grow + "}" + t)
                        else:
                            text_parts.append(("{" + own + "}" if own else "") + t + (r"{\r}" if own else ""))
                            box_parts.append("{" + own + r"\1a&HFF&\3a&HFF&\4a&HFF&}" + t)
                    if style == "box":  # lapis bawah: kotak solid hanya di kata aktif
                        add(0, s, e, "CapBox", " ".join(box_parts))
                    add(1, s, e, "Cap", " ".join(text_parts))

    # ---- judul pembuka
    if ttl["enabled"] and title.strip():
        preset = ttl.get("preset", "bar")
        t_end = duration if not ttl.get("duration") else min(float(ttl["duration"]), duration)
        style = {"bar": "TitleBar", "outline": "TitleOutline", "neon": "TitleNeon", "clean": "TitleClean"}.get(preset, "TitleBar")
        fx = r"{\fad(200,0)\frz-2}" if preset == "bar" else r"{\fad(200,0)\blur3}" if preset == "neon" else r"{\fad(200,0)}"
        add(2, 0, t_end, style, fx + _esc(title.upper() if preset != "clean" else title))
        if preset == "neon":  # lapisan teks tajam di atas glow
            add(3, 0, t_end, style, r"{\fad(200,0)\bord0}" + _esc(title.upper()))

    # ---- watermark teks
    if wm["enabled"] and wm.get("text") and not wm.get("image"):
        an = {"tl": 7, "tr": 9, "bl": 1, "br": 3, "c": 5}.get(wm["position"], 3)
        mx, my = int(40 * scale), int(H * 0.05)
        pos = {7: (mx, my), 9: (W - mx, my), 1: (mx, H - my), 3: (W - mx, H - my), 5: (W // 2, H // 2)}[an]
        add(4, 0, duration, "Mark", r"{\an" + str(an) + r"\pos(" + f"{pos[0]},{pos[1]}" + ")}" + _esc(wm["text"]))

    head = (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {W}\nPlayResY: {H}\nYCbCr Matrix: TV.709\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n" + "\n".join(styles) +
        "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    return head + "\n".join(ev) + "\n"


def _srt_ts(t: float) -> str:
    t = max(t, 0)
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(words: list[dict], per_line: int = 3) -> str:
    """Subtitle .srt standar (untuk diunggah terpisah ke YouTube/TikTok)."""
    lines = chunk_words(words, max(per_line, 4))
    out = []
    for i, line in enumerate(lines):
        end = line[-1]["e"] + 0.15
        if i + 1 < len(lines):
            end = min(end, lines[i + 1][0]["s"])
        out.append(f"{i + 1}\n{_srt_ts(line[0]['s'])} --> {_srt_ts(end)}\n{' '.join(w['w'] for w in line)}\n")
    return "\n".join(out)
