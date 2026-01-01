#!/usr/bin/env bash
set -e

# Zum Verzeichnis des Scripts wechseln
cd "$(dirname "$0")"

# venv aktivieren
source venv/bin/activate

# Flask-Server starten (im Hintergrund)
python epg_mapper_web.py &
FLASK_PID=$!

# Auf Server warten (Port anpassen!)
HOST="127.0.0.1"
PORT="8081"

echo "Warte auf Flask-Server auf $HOST:$PORT ..."

until nc -z "$HOST" "$PORT"; do
  sleep 0.5
done

echo "Flask-Server läuft."

# URL im Browser öffnen
xdg-open "http://$HOST:$PORT" >/dev/null 2>&1 &

# Flask-Prozess im Vordergrund halten
wait "$FLASK_PID"

