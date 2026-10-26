# ClipperCuan — landing page clipper

Situs statis (HTML + CSS + JS murni, tanpa build step) untuk produk AI clipper desktop.
Strukturnya terinspirasi landing page clipper "sekali bayar" yang umum, tetapi **semua kode, teks, dan visual ditulis ulang** (tidak menyalin aset, video, atau testimoni pihak lain).

## Jalankan
```bash
cd site && python3 -m http.server 8080   # lalu buka http://localhost:8080
```
Bisa langsung di-deploy ke Netlify / Cloudflare Pages / Vercel / GitHub Pages (folder `site/`).

## Yang WAJIB Anda ganti — `site/config.js`
- `brand`, `price`, `priceOriginal`
- `checkoutUrl` (Lynk.id / Mayar / Xendit dll.), `telegramUrl`, `instagramUrl`, `email`
- `testimonials`: ganti dengan testimoni **asli** dan izin pengirim; hapus `sample:true`
- `communityCount`: isi hanya angka nyata, atau biarkan kosong
- `faq` (termasuk kebijakan refund)
Selama `checkoutUrl` masih placeholder, tombol beli menampilkan peringatan, bukan membuka link.

## Fitur situs
Promo bar + countdown harian (reset 00.00 WIB, bisa diubah), nav sticky + scrollspy + progress, hero + simulasi tempel link, 12 demo interaktif (caption per kata, before/after gaming & judul, editor kata, watermark, galeri, smart-crop keyframe, orientasi, dll.), tabel perbandingan, slider testimoni + dialog, kebutuhan sistem (auto-pilih OS), kalkulator harga, FAQ aksesibel, tombol beli sticky di mobile, mode hemat animasi, `prefers-reduced-motion`.

## Mengganti visual
Mockup memakai CSS murni. Untuk memakai cuplikan hasil asli, taruh `mp4/jpg` di `site/assets/` dan ganti isi `.phone .screen` dengan `<video muted loop playsinline autoplay>`.

## Catatan
- Aplikasi clipper itu sendiri (AI, render, lisensi) **bukan** bagian repo ini; ini hanya situs pemasarannya.
- Klaim ("No.1", jumlah komunitas, perbandingan kompetitor) harus bisa Anda buktikan sebelum dipublikasikan.
- Skill REA tersedia di `.claude/skills/reverse-engineer-anything/` (MIT, lihat `LICENSE-REA`).
