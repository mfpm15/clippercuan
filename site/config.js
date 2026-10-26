/* ============================================================
   KONFIGURASI SITUS — ubah di sini, tidak perlu menyentuh HTML.
   Semua teks bertanda data-cfg="..." di index.html membaca file ini.
   ============================================================ */
window.SITE = {
  brand: "ClipperCuan",
  brandTag: "Studio Klip Kreator",
  tagline: "Satu link video jadi puluhan klip siap upload.",

  // Harga (angka rupiah, bukan teks)
  price: 149000,
  priceOriginal: 599000,
  priceNote: "1 lisensi untuk 1 perangkat",

  // Tautan penting — GANTI dengan milik Anda
  checkoutUrl: "https://lynk.id/username-anda/checkout",
  telegramUrl: "https://t.me/username_anda",
  instagramUrl: "https://instagram.com/username_anda",
  email: "halo@domainanda.com",
  downloadNote: "License key dan link download Mac/Windows dikirim ke email.",

  // Promo harian: countdown reset 00.00 zona waktu di bawah (WIB = +7)
  promoTzOffsetHours: 7,
  promoLabel: "Promo harian · reset 00.00 WIB",
  // Jika true, harga promo hanya tampil saat countdown berjalan (selalu true = promo abadi harian)
  showPromo: true,

  // Angka sosial — isi dengan angka NYATA Anda atau kosongkan ("")
  communityCount: "",   // contoh: "300+"
  contactSupportText: "Support lewat komunitas Telegram",

  // Analytics opsional: isi untuk mencatat klik tombol beli ke endpoint Anda (POST JSON)
  trackEndpoint: "",

  // Testimoni — GANTI dengan testimoni asli (izin pengirim wajib).
  // Biarkan sample:true selama masih contoh; situs akan menampilkan label "Contoh".
  testimonials: [
    { name: "Nama Pengguna 1", role: "Kreator podcast", text: "Tulis testimoni asli di sini. Ceritakan hasil nyata yang kamu rasakan setelah memakai alatnya.", sample: true },
    { name: "Nama Pengguna 2", role: "Streamer gaming", text: "Split screen facecam + gameplay jadi satu klik. Waktu edit turun jauh.", sample: true },
    { name: "Nama Pengguna 3", role: "Edukator", text: "Caption per kata bikin materi lebih mudah diikuti penonton.", sample: true },
    { name: "Nama Pengguna 4", role: "Freelance editor", text: "Satu lisensi, tanpa tagihan bulanan. Cocok buat yang ngerjain banyak klien.", sample: true },
    { name: "Nama Pengguna 5", role: "Pemilik channel", text: "Update fitur rutin dan jawaban support cepat di komunitas.", sample: true }
  ],

  faq: [
    ["Ini benar-benar sekali bayar?", "Ya. Satu kali pembayaran untuk akses lifetime di 1 perangkat. Tidak ada biaya langganan bulanan, dan update fitur termasuk."],
    ["Apa yang saya terima setelah beli?", "License key dan link download macOS/Windows dikirim ke email. Ikuti petunjuk aktivasi, lalu gabung komunitas jika butuh bantuan."],
    ["Perlu memasang API key atau dependency?", "Tidak. Aplikasi sudah membawa semua yang dibutuhkan, jadi tidak perlu memasang Node.js, Python, atau FFmpeg secara manual."],
    ["Laptop saya bisa menjalankannya?", "Minimum RAM 8 GB, disarankan 16 GB. Mendukung macOS 12+ (Apple Silicon/Intel) dan Windows 10/11 64-bit. Kecepatan proses mengikuti kemampuan perangkat."],
    ["Bisa edit caption dan klip gaming?", "Bisa. Ada editor per kata, preset font dan judul, highlight, animasi, crop keyframe, serta split screen untuk facecam + gameplay."],
    ["Kalau saya butuh bantuan?", "Tanya langsung di komunitas Telegram. Pertanyaan soal penggunaan, kendala, dan update dijawab oleh tim pengembang."],
    ["Bagaimana pembayarannya?", "Checkout lewat halaman pembayaran dengan QRIS, e-wallet, transfer bank, atau kartu yang tersedia."],
    ["Bisa refund?", "Atur kebijakan Anda di sini. Contoh: garansi 7 hari jika aplikasi tidak bisa berjalan di perangkat yang memenuhi syarat."]
  ]
};
