# ClipperCuan — aplikasi AI clipper lokal

Ubah video panjang (link YouTube/TikTok/IG atau file) jadi klip vertikal siap upload, **di laptop sendiri**:
tanpa langganan, tanpa kuota, tanpa upload ke cloud.

## Cara pakai (sekali klik)
1. Pasang **Python 3.10–3.12** dari https://www.python.org/downloads/ (Windows: centang *Add Python to PATH*).
2. Buka folder `app/` lalu:
   - **Windows:** klik dua kali `start.bat`
   - **macOS:** klik dua kali `start.command` (pertama kali: klik kanan → Open)
   - **Linux:** `./app/start.sh`
3. Pertama kali akan memasang komponen (±1–5 menit). Browser terbuka otomatis ke `http://127.0.0.1:8765`.
4. Tempel link / pilih file → atur gaya → **Mulai generate klip**.

FFmpeg sudah ikut terpasang otomatis. Model transkripsi Whisper diunduh sekali saat pertama dipakai (small ±480 MB).
Hasil tersimpan di folder `~/ClipperCuan/projects/` (tombol **Buka folder** di aplikasi).

## Fitur
| Fitur | Keterangan |
|---|---|
| Sumber video | Link YouTube/TikTok/Instagram/dll (yt-dlp, maks 1080p) atau file lokal (drag & drop) |
| Transkripsi | Whisper lokal, timestamp per kata, 14+ bahasa + auto-detect, opsi terjemah ke Inggris |
| Cari momen | Skor hook (pertanyaan/angka/kata pemicu), kata emosional, energi audio, tempo bicara, kalimat utuh |
| Judul pembuka | Otomatis dari kalimat paling kuat; preset Bar / Outline / Neon / Clean |
| Caption | Box highlight, Word by word, Karaoke, Clean · 8 font · warna · ukuran · posisi · animasi pop |
| Format | Portrait 9:16, Square 1:1, Blur background, Split gaming (facecam + gameplay), Landscape |
| Smart crop | Ikuti wajah otomatis + editor keyframe manual (geser kotak, timeline) |
| Watermark | Teks atau logo PNG, posisi & transparansi |
| Editor klip | Ubah judul, potong ulang (mulai/selesai), perbaiki ejaan caption per kata, ganti format per klip |
| Galeri & riwayat | Preview, download, render ulang, ubah gaya semua klip sekaligus, cari & hapus proyek |
| AI router (opsional) | 9router / API kompatibel OpenAI untuk memilih momen & judul (mati secara default) |
| Mode CLI | `python -m clipper cli <link/file> --clips 5 --layout portrait` |

## Kebutuhan perangkat
RAM 8 GB (disarankan 16 GB), Windows 10/11 64-bit, macOS 12+ (Intel/Apple Silicon), atau Linux. GPU NVIDIA dipakai otomatis jika ada.
Perkiraan waktu (CPU 4 core, model *small*): video 2 menit ≈ 1–1,5 menit untuk 3 klip.

## AI router (nanti)
Pengaturan → AI router: isi Base URL 9router (default `http://localhost:20128/v1`, sesuaikan dengan dashboard 9router),
API key, klik **Tes koneksi**, pilih model (mis. model pintar untuk pemilih momen, model cepat untuk judul). Jika router mati,
aplikasi otomatis kembali ke skor lokal.

## Struktur
```
app/
  start.bat / start.command / start.sh   installer + launcher
  requirements.txt
  clipper/
    download.py    ambil video (yt-dlp / file)
    transcribe.py  Whisper + timestamp kata
    highlights.py  penilaian & pemilihan momen
    llm.py         klien 9router/OpenAI-compatible (opsional)
    facetrack.py   smart crop wajah → keyframe
    captions.py    subtitle ASS (caption/judul/watermark)
    render.py      ffmpeg: crop/blur/split + burn-in
    project.py     pipeline, antrean, riwayat, edit
    server.py      API lokal (127.0.0.1)
    web/           UI aplikasi
    fonts/         font OFL untuk caption
docs/feature-map.md  peta fitur referensi → implementasi
site/                landing page (opsional, untuk jualan)
```

## Lisensi komponen
Whisper (MIT), faster-whisper (MIT), yt-dlp (Unlicense), FFmpeg (LGPL/GPL via imageio-ffmpeg), OpenCV (Apache-2.0),
font di `app/clipper/fonts` (SIL OFL). Pastikan Anda punya hak atas video yang Anda klip.
