"""Titik masuk untuk paket desktop (PyInstaller): ClipperCuan.exe / ClipperCuan (macOS)."""
import multiprocessing

from clipper.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
