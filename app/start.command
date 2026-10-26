#!/bin/bash
# macOS: klik dua kali file ini. Linux: ./start.command
cd "$(dirname "$0")" || exit 1
PY=python3
if ! command -v $PY >/dev/null 2>&1 || ! $PY -c 'import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)'; then
  echo "Python 3.10+ belum terpasang. Unduh dari https://www.python.org/downloads/ lalu jalankan file ini lagi."
  read -r -p "Tekan Enter untuk keluar"; exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "[1/2] Menyiapkan lingkungan pertama kali, mohon tunggu beberapa menit..."
  $PY -m venv .venv && .venv/bin/python -m pip install --upgrade pip >/dev/null && .venv/bin/python -m pip install -r requirements.txt \
    || { echo "Instalasi gagal. Periksa koneksi internet lalu coba lagi."; read -r -p "Tekan Enter"; exit 1; }
fi
echo "Memperbarui pengunduh video..."
.venv/bin/python -m pip install -q -U yt-dlp
echo "[2/2] Membuka ClipperCuan..."
exec .venv/bin/python -m clipper "$@"
