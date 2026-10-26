# Peta fitur: referensi → implementasi

Disusun dengan alur skill *reverse-engineer-anything* (REA): checklist pertanyaan → bukti → kesimpulan → status.
Sumber bukti hanya halaman publik socialvisuals.pro (HTML/CSS/JS yang diunduh). Installer aplikasi referensi
**tidak tersedia** (berbayar, dikirim via email), jadi tidak ada analisis binary; seluruh kode ClipperCuan ditulis orisinal.

| # | Fitur yang diklaim di situs referensi | Bukti (bagian halaman) | Implementasi ClipperCuan | Status |
|---|---|---|---|---|
| 1 | Link YouTube → puluhan klip | hero, harga "Olah video panjang dari link YouTube atau file lokal" | `download.py` (yt-dlp) + `highlights.py` | ✅ |
| 2 | Proses di perangkat, tanpa API key/dependency manual | tabel compare "Di perangkat", FAQ #3 | Whisper lokal, ffmpeg via pip, launcher auto-install | ✅ |
| 3 | Dashboard: preview + pengaturan + hasil | fitur 01 | UI `web/` (proyek, galeri, editor) | ✅ |
| 4 | Gaming split screen (facecam + gameplay) | fitur 02 | layout `split` + editor visual seret kotak facecam/gameplay | ✅ |
| 5 | Multi-language + auto-detect | fitur 03 | pilihan bahasa Whisper + terjemah ke Inggris | ✅ |
| 6 | Preset font & caption, box highlight, animasi | fitur 04, hero | `captions.py` box/wbw/karaoke/clean, 8 font, pop | ✅ |
| 7 | Preset title / generate title | fitur 05 | judul otomatis + preset Bar/Outline/Neon/Clean (+AI opsional) | ✅ |
| 8 | Custom editor per kata | fitur 06 | dialog edit kata: ejaan, pilih beberapa kata, warna & ukuran per kata | ✅ |
| 9 | Custom watermark teks & gambar | fitur 07 | teks (ASS) + logo PNG (overlay) | ✅ |
| 10 | History gallery | fitur 08 | halaman Riwayat (cari, buka, hapus) | ✅ |
| 11 | Clip gallery: review, edit judul, render | fitur 09 | kartu klip: judul, mulai/selesai, render ulang, download | ✅ |
| 12 | Clip options: crop mode, title, font sebelum render | fitur 10 | form proyek + "Ubah gaya semua klip" + format per klip | ✅ |
| 13 | Smart crop dengan keyframe | fitur 11 | `facetrack.py` (wajah) + editor keyframe manual | ✅ |
| 14 | Multi-orientation portrait/square/blur | fitur 12 | layout portrait/square/blur/landscape | ✅ |
| 15 | Lisensi 1 perangkat, aktivasi | FAQ #2 | tidak diperlukan (aplikasi milik sendiri) | — |

Fitur tambahan di luar referensi dan usulan berikutnya: lihat [usulan-fitur.md](usulan-fitur.md).
