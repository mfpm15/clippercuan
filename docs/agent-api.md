# ClipperCuan untuk AI agent

Semua proses bisa berjalan tanpa klik. Ada empat jalur; pilih yang paling cocok dengan agent kamu.
Menu **⚡ AI Agent & otomatisasi** di aplikasi menampilkan konfigurasi siap salin untuk komputermu.

## 1. MCP (disarankan untuk Claude, Cursor, dan agent berbasis MCP)

```json
{
  "mcpServers": {
    "clippercuan": {
      "command": "C:/ClipperCuan/ClipperCuan.exe",
      "args": ["mcp"]
    }
  }
}
```
Dari kode sumber: `"command": "<folder>/.venv/Scripts/python.exe", "args": ["-m", "clipper", "mcp"], "cwd": "<folder>/app"`.

Server MCP menyalakan server lokal ClipperCuan secara otomatis bila belum berjalan; proyek dari agent juga tampil di UI.
Untuk server cloud tambahkan `"env": {"CLIPPER_URL": "https://…", "CLIPPER_TOKEN": "…"}` (lihat [cloud.md](cloud.md)).
`transcriber`: `auto` (YouTube → API cloud → Whisper lokal) · `youtube` · `api` · `local`.

| Tool | Fungsi |
|---|---|
| `create_clips(source, clip_count, layout, template, language, min_sec, max_sec, caption_style, cut_silence, emoji, transcriber, extra_settings, wait, timeout_sec)` | Buat klip dari link/file. `wait=true` → kembali setelah selesai berisi path video |
| `get_project(project_id)` | Status, progres, daftar klip (path MP4/SRT/thumbnail, judul, caption, hashtag, skor, alasan) |
| `wait_for_project(project_id, timeout_sec)` | Tunggu sampai proyek & render ulang selesai |
| `list_projects(limit)` | Proyek terbaru |
| `edit_clip(project_id, clip_id, title, start, end, layout, caption, hashtags)` | Ubah klip (render ulang otomatis bila visual berubah) |
| `add_clip(project_id, start, end, title)` / `delete_clip(project_id, clip_id)` | Klip manual / hapus klip |
| `restyle_project(project_id, settings)` | Render ulang semua klip dengan gaya baru |
| `export_project(project_id, folder)` | Ekspor MP4 + SRT + `caption-posting.txt` ke folder, atau ZIP |
| `list_templates()` / `system_check()` | Template gaya / kesiapan sistem |

Contoh perintah ke agent:
> Buat 5 klip dari https://youtu.be/xxxx pakai template "Podcast Kuning" dengan emoji dan potong jeda, tunggu sampai selesai, lalu ekspor ke D:/Konten dan kirimkan caption + hashtag tiap klip.

## 2. CLI (skrip, cron, agent berbasis terminal)

```bash
ClipperCuan.exe cli "https://youtu.be/xxxx" --clips 5 --template "Podcast Kuning" --emoji --cut-silence --export "D:/Konten" --json
# dari kode sumber:  python -m clipper cli ... (di folder app/)
```
`--json` mencetak ringkasan hasil ke stdout (log progres ke stderr). Kode keluar `0` = berhasil.
Opsi lain: `--subtitle auto|youtube|api|local`, `--layout portrait|square|blur|split|landscape`, `--caption box|wbw|karaoke|clean`, `--lang id`, `--model tiny|base|small|medium|large-v3`, `--min/--max`, `--settings '{"title":{"preset":"neon"}}'`.

## 3. REST API (n8n, Make, agent HTTP)

Server lokal: `http://127.0.0.1:8765` · dokumentasi interaktif OpenAPI: `http://127.0.0.1:8765/docs`

```
POST /api/projects                 {"source": "https://youtu.be/xxxx", "settings": {"clip_count": 5}}
GET  /api/projects/{id}/summary    → status, progress, clips[].video_path / srt_path / caption / hashtags
PATCH /api/projects/{id}/clips/{cid}  {"changes": {"title": "…"}, "rerender": true}
POST /api/projects/{id}/rerender   {"settings": {"layout": "blur"}}
POST /api/projects/{id}/export     {"folder": "D:/Konten"}
GET  /api/templates   ·   GET /api/system   ·   POST /api/automation/inbox/scan
```
Server hanya mendengarkan `127.0.0.1` (tidak terbuka ke jaringan).

## 4. Tanpa sentuhan: webhook, inbox, ekspor otomatis

Atur di menu **AI Agent & otomatisasi**:

- **Webhook** — `POST` JSON ke URL kamu setiap ada event:
  `project.done`, `project.error`, `project.cancelled`, `project.updated` (setelah render ulang selesai).
  ```json
  {"event": "project.done", "project_id": "20261026-…", "title": "…", "status": "done",
   "folder": "…/projects/20261026-…", "clips": [{"id": "clip_01", "score": 97, "title": "…",
   "video_path": "…/clip_01.mp4", "srt_path": "…/clip_01.srt", "caption": "…", "hashtags": ["#…"]}]}
  ```
- **Folder inbox** — taruh file video di `~/ClipperCuan/inbox` → diproses otomatis dengan template pilihan,
  file asli dipindah ke `inbox/diproses`.
- **Ekspor otomatis** — hasil setiap proyek disalin ke folder pilihan (`YYYY-MM-DD Judul/01 - Judul.mp4`, `.srt`, `caption-posting.txt`).

Pengaturan per proyek juga bisa dikirim lewat `settings`: `"webhook_url"`, `"export_dir"`.
