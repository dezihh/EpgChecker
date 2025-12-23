# EpgChecker

## Übersicht

EpgChecker ist eine webbasierte Anwendung zur Verwaltung und Überprüfung von EPG (Electronic Program Guide) Daten für IPTV-Dienste. Die Anwendung ermöglicht es, XStream-Kanäle mit XML-EPG-Daten zu vergleichen und eine Programmliste zu erstellen.

## Hauptfunktionen

- **XStream API Integration**: Lädt Kanallisten von XStream/Xtream Codes Servern
- **XML EPG Verarbeitung**: Unterstützt das Laden von XML EPG-Dateien (auch .gz komprimiert) via Upload oder URL
- **Detailansicht**: Zeigt detaillierte Informationen zu XStream- und XML-Einträgen
- **Programmliste**: Erstellt eine nummerierte Liste von Kanälen mit XStream- und optional XML-Zuordnungen
- **Auto-Match**: Automatische Zuordnung von Kanälen basierend auf Namensähnlichkeit
- **Suchfunktion**: Filtert Kanäle nach Namen
- **History**: Speichert zuletzt verwendete URLs für schnellen Zugriff

## Installation

### Voraussetzungen

- Python 3.7 oder höher
- pip (Python Package Manager)

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
python epg_mapper_web.py
```

Die Anwendung ist dann unter `http://localhost:8081` erreichbar.

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

- `epg_mapper_web.py`: Hauptanwendung mit REST API Endpoints
- In-Memory Datenspeicherung für Kanäle und Zuordnungen
- Unterstützt GZ-komprimierte XML-Dateien
- Validierung und Fehlerbehandlung

### Frontend (HTML/JavaScript)

- `templates/index.html`: Single-Page Application
- Responsive Design
- Pagination für große Kanallisten
- Echtzeit-Suche und Filterung

### API Endpoints

- `GET /api/config`: Lädt Konfiguration
- `POST /api/add_history`: Fügt URL zur History hinzu
- `POST /api/upload_xml`: XML-Datei Upload
- `POST /api/load_xml_url`: XML von URL laden
- `POST /api/load_xstream`: XStream Daten laden
- `GET /api/get_channels`: Kanäle abrufen (mit Suchfilter)
- `POST /api/add_to_program_list`: Zur Programmliste hinzufügen
- `GET /api/get_program_list`: Programmliste abrufen
- `POST /api/auto_match`: Automatische Zuordnung

## Konfiguration

Die Konfiguration wird in `config.json` gespeichert und enthält:

- **server**: Host und Port für den Webserver
- **xstream**: Standard XStream Zugangsdaten
- **xml_epg**: Standard XML EPG URL
- **history**: Liste der zuletzt verwendeten URLs (max. 10 Einträge)

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

- Überprüfen Sie die API-Antwort in den Browser-Entwicklertools (F12)
- Prüfen Sie die Server-Logs für Fehlermeldungen

## Technische Details

### Abhängigkeiten

- **Flask**: Web-Framework
- **requests**: HTTP-Client für API-Aufrufe
- **xml.etree.ElementTree**: XML-Parser
- **gzip**: Dekompression von .gz Dateien
- **difflib**: String-Ähnlichkeitsvergleich für Auto-Match

### Unterstützte Formate

- **XStream API**: JSON Response vom `/player_api.php?action=get_live_streams` Endpoint
- **XML EPG**: Standard XMLTV Format mit `<channel>` Elementen
- **Kompression**: GZ-komprimierte Dateien werden automatisch erkannt und dekomprimiert

## Lizenz

Siehe LICENSE Datei für Details.

## Mitwirken

Beiträge sind willkommen! Bitte erstellen Sie einen Pull Request oder öffnen Sie ein Issue für Verbesserungsvorschläge.
