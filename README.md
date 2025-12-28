# EpgChecker

## Übersicht

EpgChecker ist eine webbasierte Anwendung zur Verwaltung, Prüfung und Vorschau von EPG (Electronic Program Guide) Daten für IPTV-Dienste. Die Anwendung lädt XStream-Kanäle, verarbeitet XMLTV-EPG (auch .gz), vergleicht `epg_channel_id` gegen das EPG und kann Live-Streams direkt im Browser (HLS) oder per Proxy mit AAC-Audio abspielen.

## Hauptfunktionen

- **XStream API Integration**: Lädt Kanallisten von XStream/Xtream Codes Servern
- **XMLTV EPG Verarbeitung**: Laden per Upload/URL; automatische Erkennung und Dekomprimierung von `.gz`
- **EPG-Validierung (offline)**: Prüft `epg_channel_id` gegen das geladene XML (Programme zählen, Status je Kanal)
- **EPG-Auszug**: Schneller Raw-Auszug von Programmen einer EPG-ID (`/api/get_epg_programs`)
- **Live-Stream Wiedergabe**:
  - Direktes HLS oder TS im Browser
  - **ffmpeg AAC-Proxy (HLS)** für kompatibles Audio mit Track-Auswahl
  - Audio-Track-Inspektion via `ffprobe`
- **Programmliste**: Nummerierte Liste XStream/XML-Zuordnung; Anzeige als Tabelle
- **Auto-Match**: Namensähnlichkeit (SequenceMatcher) zur schnellen Zuordnung
- **Suche & Pagination**: Filter und performante Anzeige für große Listen
- **EPG Cache**: Dateien im Verzeichnis `data/epg_cache/` mit Metadaten, Laden/Löschen über UI

## Installation

### Voraussetzungen

- Python 3.8 oder höher
- pip (Python Package Manager)
- Systemweite Tools: `ffmpeg` und `ffprobe` (für Proxy/Audio-Analyse)

### Schritt-für-Schritt Installation

1. Repository klonen oder herunterladen:
```bash
git clone https://github.com/dezihh/EpgChecker.git
cd EpgChecker
```

2. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

3. Konfigurationsdatei erstellen (optional):
```bash
cp config.json.example config.json
```

4. `config.json` bearbeiten und Ihre Zugangsdaten eintragen (optional):
```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8081
  },
  "xstream": {
    "url": "http://ihr-server:port",
    "username": "ihr-username",
    "password": "ihr-password"
  },
  "xml_epg": {
    "url": "http://example.com/epg.xml.gz"
  }
}
```

## Verwendung

### Server starten

```bash
python3 epg_mapper_web.py
```

Die Anwendung ist dann unter `http://localhost:8081` erreichbar (Konfiguration in `config.json`).

### XStream Daten laden

1. Server-URL eingeben (z.B. `http://192.168.1.100:8080`)
   - **Wichtig**: Nur die Basis-URL ohne `/player_api.php` angeben
2. Username und Password eingeben
3. Auf "XStream Laden" klicken

### XML EPG Daten laden

**Option 1: Von URL laden**
1. XML EPG URL eingeben (unterstützt .xml und .gz Dateien)
2. Auf "Von URL laden" klicken

**Option 2: Datei hochladen**
1. Datei auswählen (XML oder GZ)
2. Auf "Datei hochladen" klicken

### Detailansicht verwenden

- Klicken Sie auf den "Details anzeigen" Button bei einem XStream- oder XML-Eintrag
- Ein Modal-Dialog zeigt alle verfügbaren Informationen für den ausgewählten Kanal

### Programmliste erstellen

1. Wählen Sie einen XStream-Eintrag aus
2. Geben Sie eine eindeutige Nummer in das Eingabefeld "Nr." ein
3. Optional: Wählen Sie einen passenden XML-Eintrag aus und geben Sie die gleiche Nummer ein
4. Klicken Sie auf "Zur Programmliste hinzufügen"
5. Wiederholen Sie dies für weitere Kanäle
6. Klicken Sie auf "Programmliste anzeigen", um die erstellte Liste als HTML-Tabelle anzuzeigen

Die Programmliste enthält folgende Spalten:
- Nummer (eindeutige ID)
- XStream Sendername
- XStream EPG ID
- XML Sendername (optional)
- XML EPG ID (optional)
- XML Dateiname (optional)

### Auto-Match Funktion

Die Auto-Match Funktion vergleicht automatisch die Namen von XStream- und XML-Kanälen und erstellt Zuordnungen bei hoher Übereinstimmung (> 80%).

1. Stellen Sie sicher, dass sowohl XStream- als auch XML-Daten geladen sind
2. Klicken Sie auf "✨ Auto-Match"
3. Die Anwendung zeigt die Anzahl der gefundenen Übereinstimmungen an

## Architektur

### Backend (Flask)

- [epg_mapper_web.py](epg_mapper_web.py): Hauptanwendung mit REST API Endpoints
- [epg_utils.py](epg_utils.py): Wiederverwendbare Hilfsfunktionen (XML-Parsen, Programmzählung, Cache-Metadaten, Filename-Sanitizer, gzip-Erkennung)
- In-Memory Datenspeicherung für Kanäle und Zuordnungen
- Unterstützt GZ-komprimierte XML-Dateien; Offline-Validierung; HLS-Proxy via ffmpeg

### Frontend (HTML/JavaScript)

- [templates/index.html](templates/index.html): Single-Page Application
- [static/style.css](static/style.css): Ausgelagerte Styles für bessere Übersicht
- Responsive Design, Pagination, Suche, Modale, Player (HLS.js)

### API Endpoints (Auswahl)
- `POST /api/load_xstream_and_epg`: Lädt XStream-Senderliste und XMLTV-EPG gemeinsam und persistiert beide

- `GET /api/config`: Konfiguration laden
- `POST /api/add_history`: URL zur History hinzufügen
- `POST /api/upload_xml`: XML-Datei Upload (auch `.gz`)
- `POST /api/load_xml_url`: XML von URL laden
- `POST /api/load_xstream`: XStream Daten laden
- `GET /api/get_channels`: Kanäle abrufen (mit Suchfilter)
- `POST /api/add_to_program_list`: Zur Programmliste hinzufügen
- `GET /api/get_program_list`: Programmliste abrufen
- `POST /api/auto_match`: Automatische Zuordnung
- `POST /api/download_epg_bulk`: Einmaliges Laden des XMLTV von XStream (Login)
- `POST /api/validate_epg_offline`: EPG-Validierung gegen gecachte XML
- `GET /api/get_epg_programs?epg_id=...`: Raw-Programme für EPG-ID (Limit)
- `GET /api/export_xml`: XML/Original exportieren
- `GET /api/export_xstream`: XStream JSON exportieren
- `GET /api/list_cache`: Cache-Dateien auflisten
- `POST /api/load_from_cache`: XML aus Cache laden
- `POST /api/delete_cache_file`: Cache-Datei löschen
 - `GET /api/load_last_cache`: Letzte geladene XStream-/EPG-Daten aus `data/epg_cache/` wiederherstellen
- `GET /api/inspect_stream?stream_id=...`: Audio-Track-Inspektion via ffprobe
- `POST /api/start_hls_proxy`: ffmpeg-HLS-Proxy starten (AAC)
- `GET /api/proxy_hls/<id>/index.m3u8`: HLS-Playlist aus Proxy
- `GET /api/proxy_hls/<id>/<segment>`: HLS-Segmente aus Proxy

## Konfiguration

Die Konfiguration wird in `config.json` gespeichert und enthält:

- **server**: Host und Port für den Webserver
- **xstream**: Standard XStream Zugangsdaten
- **xml_epg**: Standard XML EPG URL
- **history**: Liste der zuletzt verwendeten URLs (max. 10 Einträge)

## Sicherheitshinweise

- Die Anwendung lädt Daten von benutzerdefinierten URLs (XStream API und XML EPG)
- **Verwenden Sie nur vertrauenswürdige URLs** von bekannten Quellen
- Die Anwendung ist für den Einsatz in lokalen Netzwerken oder vertrauenswürdigen Umgebungen konzipiert
- Für den produktiven Einsatz in öffentlichen Netzwerken sollten zusätzliche Sicherheitsmaßnahmen implementiert werden (z.B. URL-Allowlist, Authentifizierung)

## Fehlerbehebung

### XStream lädt nicht

- Überprüfen Sie die URL (ohne `/player_api.php`)
- Prüfen Sie Username und Password
- Stellen Sie sicher, dass Ihre IP-Adresse auf dem Server freigeschaltet ist
- Überprüfen Sie die Server-Erreichbarkeit

### XML lädt nicht

- Bei .gz Dateien: Stellen Sie sicher, dass die Datei korrekt komprimiert ist
- Überprüfen Sie die XML-Struktur (sollte `<channel>` Elemente enthalten)
- Prüfen Sie die URL-Erreichbarkeit

### Leere Kanallisten
### Daten nach Neustart nicht sichtbar

- Die Anwendung schreibt die letzten geladenen Dateien nach `data/epg_cache/`:
  - `last_xstream.json`: XStream-Liste
  - `last_epg.xml`: EPG (immer dekomprimiert, UTF-8)
  - optional `last_epg_raw.xml.gz`: falls EPG komprimiert heruntergeladen wurde
- Beim Start lädt das Frontend automatisch `GET /api/load_last_cache`, um diese Daten wiederherzustellen.

### ffmpeg/ffprobe nicht gefunden

- Installieren Sie `ffmpeg`/`ffprobe` systemweit (z.B. Ubuntu/Debian):
  ```bash
  sudo apt update
  sudo apt install ffmpeg
  ```
  Prüfen: `ffmpeg -version`, `ffprobe -version`

- Überprüfen Sie die API-Antwort in den Browser-Entwicklertools (F12)
- Prüfen Sie die Server-Logs für Fehlermeldungen

## Technische Details

### Abhängigkeiten

- **Flask**: Web-Framework
- **requests**: HTTP-Client für API-Aufrufe
- **xml.etree.ElementTree**: XML-Parser
- **gzip**: Dekompression von .gz Dateien
- **difflib**: String-Ähnlichkeitsvergleich für Auto-Match
- **Hls.js** (Frontend): HLS-Wiedergabe im Browser
- **ffmpeg/ffprobe** (System): Proxy/Audio-Track-Analyse

### Unterstützte Formate

- **XStream API**: JSON Response vom `/player_api.php?action=get_live_streams` Endpoint
- **XML EPG**: Standard XMLTV Format mit `<channel>` Elementen
- **Kompression**: GZ-komprimierte Dateien werden automatisch erkannt und dekomprimiert

## Lizenz

Siehe LICENSE Datei für Details.

## Mitwirken

Beiträge sind willkommen! Bitte erstellen Sie einen Pull Request oder öffnen Sie ein Issue für Verbesserungsvorschläge.
