# ClipperCuan — server cloud (VPS, Railway, Render, Fly.io, dsb.)
#   docker build -t clippercuan .
#   docker run -d -p 8765:8765 -e CLIPPER_TOKEN=passwordkamu -v clipper-data:/data clippercuan
# Buka http://IP-SERVER:8765 (login: user bebas, password = CLIPPER_TOKEN)
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 CLIPPER_HOME=/data
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY clipper ./clipper
COPY tests ./tests

# Opsional: unduh model Whisper saat build agar run pertama cepat (docker build --build-arg WHISPER_MODEL=small .)
ARG WHISPER_MODEL=""
RUN if [ -n "$WHISPER_MODEL" ]; then python -c "from faster_whisper import WhisperModel; WhisperModel('$WHISPER_MODEL', device='cpu', compute_type='int8', download_root='/opt/models')"; fi

VOLUME /data
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request as u;r=u.Request('http://127.0.0.1:8765/api/info',headers={'Authorization':'Bearer '+os.environ.get('CLIPPER_TOKEN','')});u.urlopen(r,timeout=4)" || exit 1
CMD ["python", "-m", "clipper", "--host", "0.0.0.0", "--port", "8765", "--no-browser"]
