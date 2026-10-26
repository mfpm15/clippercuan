"""Bangun paket desktop: python build.py  → dist/ClipperCuan/ (lalu di-zip oleh CI)."""
import os
import sys

import PyInstaller.__main__

sep = os.pathsep
here = os.path.dirname(os.path.abspath(__file__))
data = [("clipper/web", "clipper/web"), ("clipper/fonts", "clipper/fonts"),
        ("clipper/emoji", "clipper/emoji"), ("clipper/models", "clipper/models")]
args = [
    os.path.join(here, "launcher.py"), "--name", "ClipperCuan", "--noconfirm", "--clean", "--onedir",
    "--distpath", os.path.join(here, "dist"), "--workpath", os.path.join(here, "build"),
    "--specpath", os.path.join(here, "build"),
    *[f"--add-data={os.path.join(here, a)}{sep}{b}" for a, b in data],
    "--collect-submodules=clipper", "--collect-submodules=uvicorn", "--collect-submodules=yt_dlp",
    "--collect-all=faster_whisper", "--collect-all=ctranslate2", "--collect-all=onnxruntime",
    "--collect-data=imageio_ffmpeg", "--collect-binaries=imageio_ffmpeg", "--collect-data=cv2",
    "--collect-data=certifi", "--hidden-import=multipart", "--hidden-import=python_multipart",
    "--exclude-module=tkinter", "--exclude-module=matplotlib",
]
if sys.platform == "darwin":
    args += ["--osx-bundle-identifier", "id.clippercuan.app"]
PyInstaller.__main__.run(args)
