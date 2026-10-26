# Menjalankan ClipperCuan tanpa membebani komputer

Ada tiga tingkat, dari yang paling ringan diubah:

## 1. Subtitle tanpa transkripsi di laptop (default: mode **Otomatis**)
Di **Proyek baru → Sumber subtitle**:

| Mode | Cara kerja | Beban laptop |
|---|---|---|
| **Otomatis** (bawaan) | Subtitle YouTube → API cloud (bila diisi) → Whisper lokal | Serendah mungkin |
| **Subtitle YouTube** | Ambil subtitle bawaan video (manual/otomatis) | Nol untuk transkripsi |
| **API cloud** | Kirim audio (dikompres ±10 MB/jam) ke layanan speech-to-text | Nol untuk transkripsi |
| **Whisper di laptop** | Transkripsi lokal, offline | Paling berat, timing paling presisi |

API cloud memakai format OpenAI `/audio/transcriptions` — atur di **Pengaturan → Transkripsi cloud**:
- **Groq** — `https://api.groq.com/openai/v1`, model `whisper-large-v3` (sangat cepat, ada kuota gratis).
- **OpenAI** — `https://api.openai.com/v1`, model `whisper-1`.
- **9router** — isi alamat 9router kamu bila router tersebut meneruskan endpoint audio.

Jika satu sumber gagal (tidak ada subtitle, kuota habis, server mati) aplikasi otomatis pindah ke sumber
berikutnya dan menampilkan peringatan di halaman proyek.

> Pemilihan momen, judul, caption & hashtag bisa memakai LLM 9router (Pengaturan → AI router).
> Memotong & me-render video tetap butuh FFmpeg yang berjalan di suatu mesin — tingkat 3 di bawah.

## 2. Hanya render di laptop
Dengan subtitle dari YouTube/API, laptop hanya mengunduh video dan me-render klip (FFmpeg) — ringan,
umumnya beberapa detik per klip.

## 3. Semua di server cloud (laptop tidak dipakai sama sekali)
Jalankan di VPS (mis. 2 vCPU / 4 GB RAM sudah cukup bila subtitle dari YouTube/API):

```bash
cd app
docker build -t clippercuan .
docker run -d --name clippercuan --restart unless-stopped -p 8765:8765 \
  -e CLIPPER_TOKEN=ganti-password-kuat -v clipper-data:/data clippercuan
```
- Buka `http://IP-SERVER:8765` → login (username bebas, password = `CLIPPER_TOKEN`).
- Tanpa Docker: `CLIPPER_TOKEN=... python -m clipper --host 0.0.0.0 --port 8765 --no-browser`
  (server menolak berjalan di jaringan tanpa password).
- Disarankan memasang HTTPS di depannya (Caddy/Nginx/Cloudflare Tunnel).

AI agent memerintah server cloud lewat MCP dari mana saja:
```json
{"mcpServers": {"clippercuan": {
  "command": "python", "args": ["-m", "clipper", "mcp"], "cwd": "<folder>/app",
  "env": {"CLIPPER_URL": "https://clipper.domainkamu.com", "CLIPPER_TOKEN": "ganti-password-kuat"}}}}
```
REST API memakai header `Authorization: Bearer <CLIPPER_TOKEN>`.

**Catatan YouTube:** YouTube sering memblokir unduhan video dari IP data center (pesan "Sign in to confirm
you're not a bot" / HTTP 403). Jika terjadi di server: gunakan VPS dengan IP yang tidak diblokir,
atau unduh videonya di tempat lain lalu taruh di folder inbox / unggah file. Subtitle YouTube biasanya
tetap bisa diambil walau unduhan video diblokir.

## Etika & hak cipta
Klip video milik orang lain hanya bila diizinkan (program clipping resmi kreator, lisensi, atau konten milik
sendiri). Platform dapat menurunkan konten atau memberi sanksi akun untuk unggahan tanpa izin.
