# Architektur & Übersicht

Diese Datei dient als technische Übersicht für schnelle Orientierung und zukünftige Änderungen.

## Module

- [epg_mapper_web.py](../epg_mapper_web.py)
  - Flask-App und alle REST-Endpoints
  - In-Memory-State: `xml_channels`, `xstream_channels`, `program_list`, `epg_program_counts`, `last_xml_*`, `last_xstream_*`
  - HLS-/TS-Proxy via ffmpeg, Audio-Track-Inspektion via ffprobe
- [epg_utils.py](../epg_utils.py)
  - Wiederverwendbare Funktionen:
    - `sanitize_filename(name)`
    - `detect_gzip_bytes(bytes)`
    - `parse_xml_channels(xml_text)`
    - `build_epg_program_counts(xml_text)`
    - Cache-Metadaten: `load_cache_metadata(dir)`, `save_cache_metadata(dir, md)`, `add_to_cache(dir, fname, path)`
- Frontend
  - [templates/index.html](../templates/index.html): UI mit HLS-Player, Modalen, Suche, Pagination
  - [static/style.css](../static/style.css): Ausgelagerte Styles

## Wichtige Endpoints

- Konfiguration/History
  - `GET /api/config`
  - `POST /api/add_history`
- XML EPG
  - `POST /api/upload_xml`
  - `POST /api/load_xml_url`
  - `GET /api/export_xml`
- XStream
  - `POST /api/load_xstream`
  - `GET /api/export_xstream`
  - `POST /api/upload_xstream`
- Listen & Zuordnung
  - `GET /api/get_channels`
  - `POST /api/add_to_program_list`
  - `GET /api/get_program_list`
  - `POST /api/remove_from_program_list`
  - `POST /api/auto_match`
- EPG Cache
  - `GET /api/list_cache`
  - `POST /api/load_from_cache`
  - `POST /api/delete_cache_file`
- EPG Prüfung/Analyse
  - `POST /api/download_epg_bulk`
  - `POST /api/validate_epg_offline`
  - `GET /api/get_epg_programs?epg_id=...&limit=...`
- Streaming
  - `GET /api/proxy_ts?stream_id=...` (TS-Proxy mit AAC Audio)
  - `GET /api/inspect_stream?stream_id=...` (Audio-Track-Analyse)
  - `POST /api/start_hls_proxy` (ffmpeg HLS Proxy mit AAC)
  - `GET /api/proxy_hls/<id>/index.m3u8`
  - `GET /api/proxy_hls/<id>/<segment>`
  - `POST /api/stop_hls_proxy`

## Datenflüsse

- XML Laden
  1. Upload/URL → `last_xml_raw`, `last_xml_content`, `last_xml_is_gz`, `last_xml_source_name`
  2. `parse_xml_channels(last_xml_content)` → `xml_channels`
  3. `build_epg_program_counts(last_xml_content)` → `epg_program_counts`
- XStream Laden
  1. API/Upload → `last_xstream_data` → `xstream_channels`
- EPG Cache
  - Beim Speichern/Laden werden Metadaten unter `data/epg_cache/metadata.json` geführt

## Leitlinien für Änderungen

- State klar halten: Modifiziere In-Memory-Listen (z.B. `xml_channels`, `xstream_channels`) **in-place** wo möglich; vermeide Schattenkopien
- Wiederverwendung: Nutze Funktionen in `epg_utils.py` für Parsing/Counts/Cache
- Fehlerbehandlung: Nutzerfreundliche JSON-Fehler; detaillierte Logs (`app.logger`)
- Performance: Für große XMLs iterativ parsen (bereits in `build_epg_program_counts` umgesetzt)
- Sicherheit: Bei Dateinamen immer `sanitize_filename` einsetzen; HTTP nur mit bekannten/vertrauenswürdigen Quellen

## Quick-Checks

- Läuft Server? `python3 epg_mapper_web.py`, öffne `http://localhost:8081`
- ffmpeg/ffprobe installiert? `ffmpeg -version`, `ffprobe -version`
- Cache-Ordner vorhanden? `data/epg_cache/` wird automatisch erstellt
- CSS geladen? Siehe `<link rel="stylesheet" href="/static/style.css">` in index.html

