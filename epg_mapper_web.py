from flask import Flask, render_template, request, jsonify, Response, send_file
import xml.etree.ElementTree as ET
import requests
import json
import io
import gzip
import os
from difflib import SequenceMatcher
from datetime import datetime
import subprocess
import threading
import tempfile
import time
import shutil

app = Flask(__name__)

# Config laden
CONFIG_FILE = 'config.json'

def load_config():
    config_path = os.path.abspath(CONFIG_FILE)
    app.logger.info(f"Loading config from: {config_path}")
    
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)
            app.logger.info(f"Config loaded: xml_epg.url = {loaded_config.get('xml_epg', {}).get('url', 'N/A')}")
            return loaded_config
    else:
        # Default Config
        default_config = {
            "server": {"host": "0.0.0.0", "port": 8081},
            "xstream": {"url": "", "username": "", "password": ""},
            "xml_epg": {"url": ""},
            "history": {"xstream_urls": [], "xml_urls": [], "max_history": 10}
        }
        save_config(default_config)
        return default_config

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

# In-Memory Storage
xml_channels = []
xstream_channels = []
program_list = []  # List of entries: [{'number': '1', 'xstream': {...} or None, 'xml': {...} or None, 'id': unique_id}, ...]
next_entry_id = 1  # Counter for unique IDs
last_xml_content = None  # Store the most recently loaded raw XML content (decompressed)
last_xstream_data = None  # Store the most recently loaded raw XStream list
last_xml_raw = None  # Store the most recently loaded raw XML bytes (original)
last_xml_is_gz = False  # Whether the last loaded XML was gzipped
last_xml_source_name = None  # Source filename or URL basename for last XML
last_xstream_source_name = None  # Source filename for last XStream load/upload
last_bulk_epg_path = None  # Last saved bulk EPG file path
epg_program_counts = {}  # channel_id -> programme count
hls_processes = {}  # stream_id -> {'proc': subprocess.Popen, 'dir': path, 'started': time}

# Cache paths
DATA_DIR = os.path.abspath('data')
HLS_TEMP_DIR = os.path.join(DATA_DIR, 'hls_temp')
EPG_CACHE_DIR = os.path.join(DATA_DIR, 'epg_cache')
CACHE_METADATA_FILE = os.path.join(EPG_CACHE_DIR, 'metadata.json')

# Create directories if they don't exist
os.makedirs(HLS_TEMP_DIR, exist_ok=True)
os.makedirs(EPG_CACHE_DIR, exist_ok=True)

hls_temp_base = HLS_TEMP_DIR


def load_cache_metadata():
    """Load cache metadata from JSON file."""
    if os.path.exists(CACHE_METADATA_FILE):
        try:
            with open(CACHE_METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f) or {}
        except Exception as e:
            app.logger.warning(f"Failed to load cache metadata: {str(e)}")
    return {}

def save_cache_metadata(metadata):
    """Save cache metadata to JSON file."""
    try:
        with open(CACHE_METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as e:
        app.logger.error(f"Failed to save cache metadata: {str(e)}")

def add_to_cache(filename, file_path):
    """Register a file in cache metadata."""
    metadata = load_cache_metadata()
    if 'files' not in metadata:
        metadata['files'] = {}
    metadata['files'][filename] = {
        'path': file_path,
        'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        'created': datetime.now().isoformat()
    }
    save_cache_metadata(metadata)

def build_epg_program_counts(xml_text: str):
    """Stream-parse XML EPG to build a map channel_id(lower) -> programme count."""
    counts = {}
    try:
        for event, elem in ET.iterparse(io.StringIO(xml_text)):
            if elem.tag == 'programme':
                ch_id = (elem.get('channel', '') or '').strip()
                if ch_id:
                    key = ch_id.lower()
                    counts[key] = counts.get(key, 0) + 1
                elem.clear()
        return counts
    except Exception as e:
        app.logger.error(f"EPG parse error: {str(e)}")
        return {}


def get_xml_text_from_memory():
    """Return XML text from last loaded/bulk content, decoding gz if needed."""
    if last_xml_content:
        return last_xml_content
    if last_xml_raw:
        try:
            if last_xml_is_gz:
                return gzip.decompress(last_xml_raw).decode('utf-8')
            return last_xml_raw.decode('utf-8')
        except Exception as e:
            app.logger.error(f"Failed to decode stored XML raw: {str(e)}")
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    # Config immer frisch aus Datei laden
    current_config = load_config()
    return jsonify(current_config)

@app.route('/api/add_history', methods=['POST'])
def add_history():
    # Config frisch laden
    current_config = load_config()
    
    data = request.json
    history_type = data.get('type')  # 'xstream' or 'xml'
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False}), 400
    
    if history_type == 'xstream':
        history_list = current_config['history']['xstream_urls']
    elif history_type == 'xml':
        history_list = current_config['history']['xml_urls']
    else:
        return jsonify({'success': False}), 400
    
    # Entferne URL falls bereits vorhanden
    if url in history_list:
        history_list.remove(url)
    
    # Füge am Anfang hinzu
    history_list.insert(0, url)
    
    # Begrenze History
    max_history = current_config['history']['max_history']
    if len(history_list) > max_history:
        history_list = history_list[:max_history]
    
    if history_type == 'xstream':
        current_config['history']['xstream_urls'] = history_list
    else:
        current_config['history']['xml_urls'] = history_list
    
    save_config(current_config)
    return jsonify({'success': True})

@app.route('/api/upload_xml', methods=['POST'])
def upload_xml():
    global xml_channels, last_xml_raw, last_xml_is_gz, last_xml_source_name
    
    if 'file' not in request.files:
        return jsonify({'error': 'Keine Datei hochgeladen'}), 400
    
    file = request.files['file']
    
    try:
        # Prüfe ob Datei komprimiert ist
        file_content = file.read()
        
        # Versuche GZ zu entpacken nur wenn es wirklich GZ ist
        is_gzipped = (file.filename.endswith('.gz') or file_content[:2] == b'\x1f\x8b')
        # Store original raw content and metadata
        last_xml_raw = file_content
        last_xml_is_gz = is_gzipped
        last_xml_source_name = file.filename or 'uploaded_epg.xml'
        
        if is_gzipped:
            try:
                content = gzip.decompress(file_content).decode('utf-8')
                app.logger.info("File decompressed from GZ format")
            except Exception as e:
                app.logger.error(f"GZ decompression failed: {str(e)}")
                # Fallback: Versuche als normale Datei
                try:
                    content = file_content.decode('utf-8')
                    app.logger.info("Fallback: Reading as plain text")
                except:
                    return jsonify({'error': f'Fehler beim Lesen der Datei: {str(e)}'}), 500
        else:
            content = file_content.decode('utf-8')
            app.logger.info("Reading as plain XML file")
        
        # Store raw (decompressed) XML for saving
        try:
            globals()['last_xml_content'] = content
        except Exception as e:
            app.logger.error(f"Failed to store last_xml_content: {str(e)}")

        root = ET.fromstring(content)
        
        xml_channels = []
        for channel in root.findall('channel'):
            ch_id = channel.get('id', '')
            display_name = channel.find('display-name')
            name = display_name.text if display_name is not None else ''
            
            xml_channels.append({
                'id': ch_id,
                'name': name
            })
        
        # Save uploaded file to cache
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        original_name = os.path.splitext(file.filename or 'uploaded_epg.xml')[0]
        cache_filename = f"{original_name}_{ts}.xml"
        cache_path = os.path.join(EPG_CACHE_DIR, cache_filename)
        with open(cache_path, 'wb') as f:
            f.write(file_content)
        add_to_cache(cache_filename, cache_path)
        
        return jsonify({
            'success': True,
            'count': len(xml_channels),
            'channels': xml_channels
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/load_xml_url', methods=['POST'])
def load_xml_url():
    global xml_channels, last_xml_content, last_xml_raw, last_xml_is_gz, last_xml_source_name
    
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL erforderlich'}), 400
    
    try:
        # Note: This makes a request to a user-provided URL, which is the intended functionality
        # for loading XML EPG data. Users should only provide trusted URLs.
        # Consider implementing URL allowlist or additional validation in production environments.
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Prüfe ob Content GZ-komprimiert ist
        content_encoding = response.headers.get('content-encoding', '').lower()
        
        # Automatische GZ-Erkennung (nur wenn wirklich GZ Magic Bytes vorhanden)
        is_gzipped = (content_encoding == 'gzip' or 
                      url.endswith('.gz') or 
                      response.content[:2] == b'\x1f\x8b')
        # Store original raw content and metadata
        last_xml_raw = response.content
        last_xml_is_gz = is_gzipped
        try:
            last_xml_source_name = os.path.basename(url) if url else None
        except Exception:
            last_xml_source_name = None
        
        if is_gzipped:
            try:
                content = gzip.decompress(response.content).decode('utf-8')
                app.logger.info("URL content decompressed from GZ format")
            except Exception as e:
                app.logger.error(f"GZ decompression failed: {str(e)}")
                # Fallback: Versuche als normale Datei
                try:
                    content = response.content.decode('utf-8')
                    app.logger.info("Fallback: Reading as plain text")
                except:
                    return jsonify({'error': f'Fehler beim Lesen der Datei: {str(e)}'}), 500
        else:
            content = response.content.decode('utf-8')
            app.logger.info("Reading as plain XML")
        
        # Store raw (decompressed) XML for saving
        try:
            last_xml_content = content
        except Exception as e:
            app.logger.error(f"Failed to store last_xml_content: {str(e)}")

        root = ET.fromstring(content)
        
        xml_channels = []
        for channel in root.findall('channel'):
            ch_id = channel.get('id', '')
            display_name = channel.find('display-name')
            name = display_name.text if display_name is not None else ''
            
            xml_channels.append({
                'id': ch_id,
                'name': name
            })
        
        # Save URL-loaded file to cache
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        url_basename = os.path.basename(url) or 'xmltv.php'
        original_name = os.path.splitext(url_basename)[0]
        cache_filename = f"{original_name}_{ts}.xml"
        cache_path = os.path.join(EPG_CACHE_DIR, cache_filename)
        with open(cache_path, 'wb') as f:
            f.write(response.content)
        add_to_cache(cache_filename, cache_path)
        
        return jsonify({
            'success': True,
            'count': len(xml_channels),
            'channels': xml_channels
        })
    
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Fehler beim Laden der URL: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/load_xstream', methods=['POST'])
def load_xstream():
    global xstream_channels, program_list, next_entry_id, last_xstream_data, last_xstream_source_name
    
    # Lösche alte Daten und Programmliste
    xstream_channels = []
    program_list = []
    next_entry_id = 1
    last_xstream_source_name = None
    
    data = request.json
    url = data.get('url', '').strip().rstrip('/')
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not all([url, username, password]):
        return jsonify({'error': 'Alle Felder müssen ausgefüllt sein'}), 400
    
    try:
        # Entferne /player_api.php falls vorhanden und baue URL neu auf
        base_url = url.replace('/player_api.php', '')
        api_url = f"{base_url}/player_api.php?username={username}&password={password}&action=get_live_streams"
        
        app.logger.info(f"Requesting XStream API: {api_url}")
        
        # Headers hinzufügen - manche Server erwarten User-Agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }
        
        try:
            response = requests.get(api_url, headers=headers, timeout=30)
            app.logger.info(f"Response Status: {response.status_code}")
            app.logger.info(f"Response Content-Type: {response.headers.get('content-type', 'unknown')}")
            app.logger.info(f"Response length: {len(response.content)} bytes")
        except requests.exceptions.Timeout:
            app.logger.error("Request timeout after 30 seconds")
            return jsonify({'error': 'Timeout: Server antwortet nicht innerhalb von 30 Sekunden'}), 500
        except requests.exceptions.ConnectionError as ce:
            app.logger.error(f"Connection error: {str(ce)}")
            return jsonify({'error': f'Verbindungsfehler: Server hat Verbindung abgelehnt. Prüfe: 1) Zugangsdaten 2) IP-Whitelist 3) Server-Erreichbarkeit. Details: {str(ce)}'}), 500
        except requests.exceptions.RequestException as re:
            app.logger.error(f"Request exception: {str(re)}")
            return jsonify({'error': f'Request-Fehler: {str(re)}'}), 500
        
        response.raise_for_status()
        
        # Prüfe ob Response JSON ist
        content_type = response.headers.get('content-type', '')
        if 'json' not in content_type.lower() and 'application/octet-stream' not in content_type.lower():
            app.logger.error(f"Response is not JSON: {response.text[:500]}")
            return jsonify({'error': f'Server antwortete mit {content_type} statt JSON. Prüfe URL, Username und Password.'}), 500
        
        try:
            data = response.json()
        except json.JSONDecodeError as je:
            app.logger.error(f"JSON decode failed. First 1000 chars: {response.text[:1000]}")
            return jsonify({'error': f'Kann JSON nicht parsen. Server-Antwort: {response.text[:200]}'}), 500
        
        # Prüfe ob Antwort eine Liste ist
        if not isinstance(data, list):
            app.logger.error(f"Response is not a list, type: {type(data)}, content: {str(data)[:500]}")
            return jsonify({'error': f'Ungültige API-Antwort (kein Array). Möglicherweise falsche Zugangsdaten. Antwort: {str(data)[:200]}'}), 500
        
        app.logger.info(f"Successfully parsed {len(data)} channels")
        
        # Keep raw data for saving
        try:
            last_xstream_data = data
            last_xstream_source_name = None
        except Exception as e:
            app.logger.error(f"Failed to store last_xstream_data: {str(e)}")

        xstream_channels = []
        for ch in data:
            # Store the complete raw channel data
            xstream_channels.append(ch)
        
        return jsonify({
            'success': True,
            'count': len(xstream_channels),
            'channels': xstream_channels
        })
    
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Request error: {str(e)}")
        return jsonify({'error': f'Fehler beim Abrufen der XStream Daten: {str(e)}'}), 500
    except json.JSONDecodeError as e:
        app.logger.error(f"JSON decode error: {str(e)}")
        return jsonify({'error': 'Server antwortete nicht mit gültigem JSON. Prüfe URL und Zugangsdaten.'}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': f'Unerwarteter Fehler: {str(e)}'}), 500

@app.route('/api/save_xstream', methods=['POST'])
def save_xstream():
    try:
        if not last_xstream_data:
            return jsonify({'success': False, 'error': 'Keine XStream Daten geladen'}), 400
        # Optional filename from request
        req = request.get_json(silent=True) or {}
        req_name = (req.get('filename') or '').strip()
        def sanitize_name(name: str):
            base = os.path.basename(name)
            return base.replace('../', '').replace('..', '')
        # Create data directory if missing
        out_dir = os.path.abspath('data')
        os.makedirs(out_dir, exist_ok=True)
        # Build filename with timestamp
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        if req_name:
            safe = sanitize_name(req_name)
            if not safe.lower().endswith('.json'):
                safe += '.json'
            out_path = os.path.join(out_dir, safe)
        else:
            out_path = os.path.join(out_dir, f'xstream_channels_{ts}.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(last_xstream_data, f, ensure_ascii=False, indent=2)
        return jsonify({'success': True, 'path': out_path})
    except Exception as e:
        app.logger.error(f"Error saving XStream data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/save_xml', methods=['POST'])
def save_xml():
    try:
        # Save raw XML content or original bytes; also save parsed channels JSON for convenience
        if not last_xml_content and not last_xml_raw:
            return jsonify({'success': False, 'error': 'Keine XML Daten geladen'}), 400
        req = request.get_json(silent=True) or {}
        req_name = (req.get('filename') or '').strip()
        save_original = bool(req.get('original', False))
        def sanitize_name(name: str):
            base = os.path.basename(name)
            return base.replace('../', '').replace('..', '')
        out_dir = os.path.abspath('data')
        os.makedirs(out_dir, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Determine filename and format
        if req_name:
            safe = sanitize_name(req_name)
            # If saving original gz, ensure .xml.gz
            if save_original and last_xml_is_gz and not safe.lower().endswith('.xml.gz'):
                safe += '.xml.gz'
            elif not safe.lower().endswith('.xml') and not safe.lower().endswith('.xml.gz'):
                safe += '.xml'
            xml_path = os.path.join(out_dir, safe)
        else:
            if save_original and last_xml_is_gz:
                xml_path = os.path.join(out_dir, f'epg_{ts}.xml.gz')
            else:
                xml_path = os.path.join(out_dir, f'epg_{ts}.xml')
        # Write XML
        if save_original and last_xml_raw is not None:
            # Write original bytes (gz or plain)
            with open(xml_path, 'wb') as f:
                f.write(last_xml_raw)
        else:
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(last_xml_content or '')
        # Parsed channels
        channels_path = os.path.join(out_dir, f'xml_channels_{ts}.json')
        with open(channels_path, 'w', encoding='utf-8') as f:
            json.dump(xml_channels, f, ensure_ascii=False, indent=2)
        return jsonify({'success': True, 'xml_path': xml_path, 'channels_path': channels_path})
    except Exception as e:
        app.logger.error(f"Error saving XML data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export_xstream', methods=['GET'])
def export_xstream():
    try:
        if not last_xstream_data:
            return jsonify({'success': False, 'error': 'Keine XStream Daten geladen'}), 400
        req_name = request.args.get('filename', '').strip()
        def sanitize_name(name: str):
            base = os.path.basename(name)
            return base.replace('../', '').replace('..', '')
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        if req_name:
            safe = sanitize_name(req_name)
            if not safe.lower().endswith('.json'):
                safe += '.json'
            fname = safe
        else:
            fname = last_xstream_source_name or f'xstream_channels_{ts}.json'
        buf = io.BytesIO()
        buf.write(json.dumps(last_xstream_data, ensure_ascii=False, indent=2).encode('utf-8'))
        buf.seek(0)
        return app.response_class(buf.read(), mimetype='application/json', headers={
            'Content-Disposition': f'attachment; filename="{fname}"'
        })
    except Exception as e:
        app.logger.error(f"Error exporting XStream data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export_xml', methods=['GET'])
def export_xml():
    try:
        if not last_xml_content and not last_xml_raw:
            return jsonify({'success': False, 'error': 'Keine XML Daten geladen'}), 400
        original = request.args.get('original', 'false').lower() in ['1', 'true', 'yes']
        req_name = request.args.get('filename', '').strip()
        def sanitize_name(name: str):
            base = os.path.basename(name)
            return base.replace('../', '').replace('..', '')
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Decide content and filename
        if original and last_xml_raw is not None:
            content_bytes = last_xml_raw
            default_name = last_xml_source_name or (f'epg_{ts}.xml.gz' if last_xml_is_gz else f'epg_{ts}.xml')
        else:
            content_bytes = (last_xml_content or '').encode('utf-8')
            default_name = f'epg_{ts}.xml'
        if req_name:
            safe = sanitize_name(req_name)
            if original and last_xml_is_gz and not safe.lower().endswith('.xml.gz'):
                safe += '.xml.gz'
            elif not safe.lower().endswith('.xml') and not safe.lower().endswith('.xml.gz'):
                safe += '.xml'
            fname = safe
        else:
            fname = default_name
        buf = io.BytesIO(content_bytes)
        buf.seek(0)
        mime = 'application/gzip' if fname.lower().endswith('.gz') else 'application/xml'
        return app.response_class(buf.read(), mimetype=mime, headers={
            'Content-Disposition': f'attachment; filename="{fname}"'
        })
    except Exception as e:
        app.logger.error(f"Error exporting XML data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/proxy_ts')
def proxy_ts():
    """Proxy a stream and transcode audio to AAC for browser compatibility.

    Query params:
      - stream_id: required XStream stream id
    """
    stream_id = request.args.get('stream_id', '').strip()
    print(f"[PROXY] Request for stream_id={stream_id}")
    if not stream_id:
        return jsonify({'error': 'stream_id erforderlich'}), 400

    cfg = load_config()
    xcfg = cfg.get('xstream', {})
    base_url = (xcfg.get('url') or '').replace('/player_api.php', '')
    username = xcfg.get('username') or ''
    password = xcfg.get('password') or ''
    if not all([base_url, username, password]):
        print("[PROXY] Missing XStream credentials")
        return jsonify({'error': 'XStream Zugangsdaten fehlen'}), 400

    source_url = f"{base_url}/live/{username}/{password}/{stream_id}.ts"
    print(f"[PROXY] Source URL: {source_url}")

    # Build ffmpeg command: copy video, transcode audio to AAC, output MPEG-TS for streaming
    cmd = [
        'ffmpeg',
        '-nostdin',
        '-loglevel', 'warning',
        '-user_agent', 'Mozilla/5.0',
        '-headers', 'Accept: */*\r\n',
        '-rw_timeout', '15000000',  # 15s
        '-reconnect', '1',
        '-reconnect_streamed', '1',
        '-reconnect_delay_max', '2',
        '-i', source_url,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-ac', '2',
        '-b:a', '128k',
        '-f', 'mpegts',
        'pipe:1'
    ]
    
    print(f"[PROXY] Starting ffmpeg...")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        print("[PROXY] ffmpeg not found")
        return jsonify({'error': 'ffmpeg nicht gefunden. Bitte ffmpeg installieren.'}), 500
    except Exception as e:
        print(f"[PROXY] ffmpeg start failed: {str(e)}")
        app.logger.error(f"ffmpeg start failed: {str(e)}")
        return jsonify({'error': f'ffmpeg Fehler: {str(e)}'}), 500

    # Try to read first chunk to detect early failures
    print("[PROXY] Attempting to read first chunk...")
    try:
        first_chunk = proc.stdout.read(8192)
        print(f"[PROXY] First chunk read: {len(first_chunk)} bytes")
    except Exception as e:
        proc.terminate()
        print(f"[PROXY] Read error: {str(e)}")
        app.logger.error(f"ffmpeg read error: {str(e)}")
        return jsonify({'error': f'ffmpeg Read-Fehler: {str(e)}'}), 500

    if not first_chunk:
        print("[PROXY] No data received from ffmpeg, checking stderr...")
        err_output = b''
        try:
            err_output = proc.stderr.read() or b''
        except Exception as e:
            app.logger.error(f"ffmpeg read tail error: {str(e)}")
        proc.terminate()
        msg = err_output.decode('utf-8', errors='ignore')[:800]
        print(f"[PROXY] ffmpeg stderr/stdout: {msg}")
        app.logger.error(f"ffmpeg delivered no data. stderr/stdout: {msg}")
        return jsonify({'error': f'ffmpeg liefert keine Daten. Details: {msg}'}), 502
    else:
        print(f"[PROXY] Stream started successfully, first chunk {len(first_chunk)} bytes")
        app.logger.info(f"proxy_ts started stream_id={stream_id}, first chunk {len(first_chunk)} bytes")

    def generate():
        try:
            yield first_chunk
            chunk_count = 1
            for chunk in iter(lambda: proc.stdout.read(8192), b''):
                if not chunk:
                    break
                chunk_count += 1
                if chunk_count % 100 == 0:
                    print(f"[PROXY] Streamed {chunk_count} chunks...")
                yield chunk
            print(f"[PROXY] Stream ended, total {chunk_count} chunks")
        finally:
            try:
                proc.terminate()
                print("[PROXY] ffmpeg terminated")
            except Exception:
                pass

    headers = {
        'Content-Type': 'video/mp2t',
        'Cache-Control': 'no-store, max-age=0'
    }
    print("[PROXY] Sending response...")
    return Response(generate(), headers=headers)

@app.route('/api/inspect_stream')
def inspect_stream():
    """Use ffprobe to inspect stream audio tracks."""
    stream_id = request.args.get('stream_id', '').strip()
    if not stream_id:
        return jsonify({'error': 'stream_id erforderlich'}), 400
    
    cfg = load_config()
    xcfg = cfg.get('xstream', {})
    base_url = (xcfg.get('url') or '').replace('/player_api.php', '')
    username = xcfg.get('username') or ''
    password = xcfg.get('password') or ''
    if not all([base_url, username, password]):
        return jsonify({'error': 'XStream Zugangsdaten fehlen'}), 400
    
    source_url = f"{base_url}/live/{username}/{password}/{stream_id}.ts"
    
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-select_streams', 'a',
        source_url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return jsonify({'error': 'ffprobe fehlgeschlagen', 'stderr': result.stderr}), 500
        
        data = json.loads(result.stdout)
        streams = data.get('streams', [])
        
        audio_tracks = []
        for i, s in enumerate(streams):
            codec = s.get('codec_name', 'unknown')
            channels = s.get('channels', 0)
            lang = s.get('tags', {}).get('language', 'und')
            audio_tracks.append({
                'index': i,
                'codec': codec,
                'channels': channels,
                'language': lang,
                'compatible': codec.lower() in ['aac', 'mp3', 'mp2']
            })
        
        return jsonify({'success': True, 'audio_tracks': audio_tracks})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'ffprobe timeout'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/start_hls_proxy', methods=['POST'])
def start_hls_proxy():
    """Start HLS transcoding for a stream (AAC audio)."""
    data = request.get_json() or {}
    stream_id = data.get('stream_id', '').strip()
    audio_track = data.get('audio_track', 0)  # Index of audio track to prioritize
    if not stream_id:
        return jsonify({'error': 'stream_id erforderlich'}), 400
    
    # Check if already running
    if stream_id in hls_processes:
        proc_info = hls_processes[stream_id]
        if proc_info['proc'].poll() is None:  # still running
            return jsonify({'success': True, 'message': 'already running'})
    
    cfg = load_config()
    xcfg = cfg.get('xstream', {})
    base_url = (xcfg.get('url') or '').replace('/player_api.php', '')
    username = xcfg.get('username') or ''
    password = xcfg.get('password') or ''
    if not all([base_url, username, password]):
        return jsonify({'error': 'XStream Zugangsdaten fehlen'}), 400
    
    source_url = f"{base_url}/live/{username}/{password}/{stream_id}.ts"
    
    # Create temp dir for this stream
    stream_dir = os.path.join(hls_temp_base, stream_id)
    os.makedirs(stream_dir, exist_ok=True)
    
    playlist_path = os.path.join(stream_dir, 'index.m3u8')
    segment_pattern = os.path.join(stream_dir, 'segment%03d.ts')
    
    # Build ffmpeg command - prioritize selected audio track for AAC transcoding
    cmd = [
        'ffmpeg',
        '-nostdin',
        '-loglevel', 'warning',
        '-user_agent', 'Mozilla/5.0',
        '-headers', 'Accept: */*\r\n',
        '-rw_timeout', '15000000',
        '-reconnect', '1',
        '-reconnect_streamed', '1',
        '-reconnect_delay_max', '2',
        '-i', source_url,
        '-map', '0:v:0',  # video
        '-map', f'0:a:{audio_track}',  # selected audio track
        '-c:v', 'copy',
        '-c:a', 'aac',  # transcode to AAC
        '-ac', '2',
        '-b:a', '128k',
        '-f', 'hls',
        '-hls_time', '2',
        '-hls_list_size', '10',
        '-hls_flags', 'delete_segments+append_list',
        '-hls_segment_type', 'mpegts',
        playlist_path
    ]
    
    print(f"[HLS] Starting ffmpeg for stream_id={stream_id}, audio_track={audio_track}")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        hls_processes[stream_id] = {'proc': proc, 'dir': stream_dir, 'started': time.time()}
        print(f"[HLS] Started, pid={proc.pid}")
        return jsonify({'success': True})
    except Exception as e:
        print(f"[HLS] Start failed: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/proxy_hls/<stream_id>/index.m3u8')
def serve_hls_playlist(stream_id):
    """Serve HLS playlist."""
    if stream_id not in hls_processes:
        return jsonify({'error': 'Stream not started'}), 404
    
    stream_dir = hls_processes[stream_id]['dir']
    playlist_path = os.path.join(stream_dir, 'index.m3u8')
    
    # Wait a bit for ffmpeg to generate playlist
    for _ in range(30):
        if os.path.exists(playlist_path):
            break
        time.sleep(0.2)
    else:
        return jsonify({'error': 'Playlist nicht gefunden'}), 404
    
    return send_file(playlist_path, mimetype='application/vnd.apple.mpegurl')


@app.route('/api/proxy_hls/<stream_id>/<segment>')
def serve_hls_segment(stream_id, segment):
    """Serve HLS segment."""
    if stream_id not in hls_processes:
        return jsonify({'error': 'Stream not started'}), 404
    
    stream_dir = hls_processes[stream_id]['dir']
    segment_path = os.path.join(stream_dir, segment)
    
    if not os.path.exists(segment_path):
        return jsonify({'error': 'Segment nicht gefunden'}), 404
    
    return send_file(segment_path, mimetype='video/mp2t')


@app.route('/api/stop_hls_proxy', methods=['POST'])
def stop_hls_proxy():
    """Stop HLS transcoding for a stream."""
    data = request.get_json() or {}
    stream_id = data.get('stream_id', '').strip()
    if not stream_id or stream_id not in hls_processes:
        return jsonify({'success': True})
    
    proc_info = hls_processes[stream_id]
    try:
        proc_info['proc'].terminate()
        print(f"[HLS] Stopped stream_id={stream_id}")
    except Exception:
        pass
    
    # Cleanup dir
    try:
        shutil.rmtree(proc_info['dir'], ignore_errors=True)
    except Exception:
        pass
    
    del hls_processes[stream_id]
    return jsonify({'success': True})

@app.route('/api/upload_xstream', methods=['POST'])
def upload_xstream():
    global xstream_channels, program_list, next_entry_id, last_xstream_data, last_xstream_source_name
    if 'file' not in request.files:
        return jsonify({'error': 'Keine Datei hochgeladen'}), 400
    file = request.files['file']
    try:
        file_content = file.read()
        filename = file.filename or 'xstream.json'
        # Detect gzip
        is_gzipped = filename.endswith('.gz') or file_content[:2] == b'\x1f\x8b'
        if is_gzipped:
            try:
                content_text = gzip.decompress(file_content).decode('utf-8')
            except Exception as e:
                return jsonify({'error': f'GZ Dekomprimierung fehlgeschlagen: {str(e)}'}), 500
        else:
            content_text = file_content.decode('utf-8')
        try:
            data = json.loads(content_text)
        except json.JSONDecodeError as je:
            return jsonify({'error': f'Ungueltiges JSON: {str(je)}'}), 400
        if not isinstance(data, list):
            return jsonify({'error': 'Erwartet eine JSON-Liste von Channels'}), 400

        # Reset and store
        xstream_channels = []
        program_list = []
        next_entry_id = 1
        last_xstream_data = data
        last_xstream_source_name = os.path.basename(filename)

        for ch in data:
            xstream_channels.append(ch)

        return jsonify({'success': True, 'count': len(xstream_channels), 'channels': xstream_channels})
    except Exception as e:
        app.logger.error(f"Error uploading XStream data: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/download_epg_bulk', methods=['POST'])
def download_epg_bulk():
    """Download XMLTV from XStream (single login) and cache for offline validation."""
    global last_xml_raw, last_xml_content, last_xml_is_gz, last_xml_source_name, last_bulk_epg_path, epg_program_counts
    try:
        cfg = load_config()
        base_url = (cfg.get('xstream', {}).get('url') or '').strip().rstrip('/')
        user = (cfg.get('xstream', {}).get('username') or '').strip()
        pwd = (cfg.get('xstream', {}).get('password') or '').strip()
        if not (base_url and user and pwd):
            return jsonify({'success': False, 'error': 'XStream Zugangsdaten in config fehlen'}), 400

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate'
        }

        # Use only XStream xmltv.php, no fallback
        base_url = base_url.replace('/player_api.php', '')
        epg_url = f"{base_url}/xmltv.php?username={user}&password={pwd}"
        app.logger.info(f"Downloading bulk EPG from XStream: {epg_url}")
        
        try:
            resp = requests.get(epg_url, timeout=60, headers=headers)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            app.logger.exception(f"Failed to fetch EPG from XStream {epg_url}")
            return jsonify({'success': False, 'error': f'XStream EPG Download fehlgeschlagen: {str(e)}'}), 500

        content = resp.content
        is_gz = resp.headers.get('content-encoding', '').lower() == 'gzip' or content[:2] == b'\x1f\x8b'
        last_xml_is_gz = is_gz
        last_xml_raw = content
        last_xml_source_name = 'xmltv.php'
        # Decode
        if is_gz:
            try:
                last_xml_content = gzip.decompress(content).decode('utf-8')
            except Exception as e:
                app.logger.error(f"GZ decode failed: {str(e)}")
                return jsonify({'success': False, 'error': f'GZ-Dekomprimierung fehlgeschlagen: {str(e)}'}), 500
        else:
            last_xml_content = content.decode('utf-8')
        # Save to disk in cache directory
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"epg_bulk_{ts}.xml.gz" if is_gz else f"epg_bulk_{ts}.xml"
        path = os.path.join(EPG_CACHE_DIR, filename)
        with open(path, 'wb') as f:
            f.write(content)
        last_bulk_epg_path = path
        add_to_cache(filename, path)
        # Build counts map
        epg_program_counts = build_epg_program_counts(last_xml_content)
        return jsonify({
            'success': True,
            'path': path,
            'channels_with_programs': len([k for k,v in epg_program_counts.items() if v>0]),
            'total_programmes': sum(epg_program_counts.values()),
            'is_gz': is_gz
        })
    except Exception as e:
        app.logger.exception(f"Error downloading bulk EPG: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/validate_epg_offline', methods=['POST'])
def validate_epg_offline():
    """Validate XStream epg_channel_id against cached XML without new logins."""
    global epg_program_counts
    try:
        xml_text = get_xml_text_from_memory()
        if not xml_text:
            return jsonify({'success': False, 'error': 'Keine EPG XML geladen. Bitte Bulk-EPG laden oder XML hochladen.'}), 400
        # Ensure counts map
        if not epg_program_counts:
            epg_program_counts = build_epg_program_counts(xml_text)
        results = []
        for ch in xstream_channels:
            epg_id_raw = ch.get('epg_channel_id') or ''
            epg_id = epg_id_raw.strip()
            epg_key = epg_id.lower()
            if not epg_id:
                results.append({
                    'stream_id': ch.get('stream_id'),
                    'name': ch.get('name', ''),
                    'epg_id': epg_id_raw,
                    'status': 'missing_epg_id',
                    'programmes': 0
                })
                continue
            if epg_key not in epg_program_counts:
                results.append({
                    'stream_id': ch.get('stream_id'),
                    'name': ch.get('name', ''),
                    'epg_id': epg_id_raw,
                    'status': 'not_found',
                    'programmes': 0
                })
            else:
                count = epg_program_counts.get(epg_key, 0)
                status = 'ok' if count > 0 else 'no_programmes'
                results.append({
                    'stream_id': ch.get('stream_id'),
                    'name': ch.get('name', ''),
                    'epg_id': epg_id_raw,
                    'status': status,
                    'programmes': count
                })
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        app.logger.error(f"Error validating EPG offline: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/get_epg_programs', methods=['GET'])
def get_epg_programs():
    """Return a small sample of programmes for a given EPG channel id from cached XML."""
    try:
        epg_id = request.args.get('epg_id', '').strip()
        limit = int(request.args.get('limit', '20'))
        if not epg_id:
            return jsonify({'success': False, 'error': 'epg_id erforderlich'}), 400
        xml_text = get_xml_text_from_memory()
        if not xml_text:
            return jsonify({'success': False, 'error': 'Keine EPG XML geladen.'}), 400
        programmes = []
        epg_key = epg_id.lower()
        found_count = 0
        try:
            for event, elem in ET.iterparse(io.StringIO(xml_text)):
                if elem.tag == 'programme':
                    ch_attr = (elem.get('channel', '') or '').strip()
                    if ch_attr and ch_attr.lower() == epg_key:
                        found_count += 1
                        title_elem = elem.find('title')
                        desc_elem = elem.find('desc')
                        title_text = (title_elem.text or '').strip() if title_elem is not None else ''
                        desc_text = (desc_elem.text or '').strip() if desc_elem is not None else ''
                        # Add programme regardless of whether title is empty or not
                        programmes.append({
                            'start': elem.get('start', ''),
                            'stop': elem.get('stop', ''),
                            'title': title_text,
                            'desc': desc_text
                        })
                        if len(programmes) >= limit:
                            elem.clear()
                            break
                    # Clear element AFTER we've extracted what we need
                    elem.clear()
        except Exception as e:
            app.logger.error(f"Error iterating programmes: {str(e)}")
        
        app.logger.info(f"get_epg_programs: Found {found_count} total for {epg_id}, returning {len(programmes)} with limit {limit}")
        return jsonify({
            'success': True, 
            'epg_id': epg_id, 
            'programmes': programmes,
            'debug_total_found': found_count
        })
    except Exception as e:
        app.logger.error(f"Error in get_epg_programs: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get_channels', methods=['GET'])
def get_channels():
    try:
        search = request.args.get('search', '').lower()
        
        filtered_xstream = [ch for ch in xstream_channels if search in ch['name'].lower()] if search else xstream_channels
        filtered_xml = [ch for ch in xml_channels if search in ch['name'].lower()] if search else xml_channels
        
        return jsonify({
            'xstream': filtered_xstream,
            'xml': filtered_xml
        })
    except Exception as e:
        app.logger.error(f"Error in get_channels: {str(e)}")
        return jsonify({
            'xstream': [],
            'xml': [],
            'error': str(e)
        }), 500

@app.route('/api/add_to_program_list', methods=['POST'])
def add_to_program_list():
    global program_list, next_entry_id
    
    try:
        data = request.json
        number = data.get('number')
        stream_id = data.get('stream_id')
        xml_id = data.get('xml_id')
        
        if not number:
            return jsonify({'error': 'Nummer erforderlich'}), 400
        
        # Find channel details
        xstream_ch = None
        xml_ch = None
        
        if stream_id:
            xstream_ch = next((x for x in xstream_channels if str(x.get('stream_id')) == str(stream_id)), None)
        
        if xml_id:
            xml_ch = next((x for x in xml_channels if str(x.get('id')) == str(xml_id)), None)
        
        # Must have at least one channel
        if not xstream_ch and not xml_ch:
            return jsonify({'error': 'Mindestens ein Kanal erforderlich'}), 400
        
        # Always append a new entry (multiple entries with same number are allowed)
        entry = {
            'id': next_entry_id,
            'number': number,
            'xstream': xstream_ch,
            'xml': xml_ch
        }
        program_list.append(entry)
        next_entry_id += 1
        
        return jsonify({'success': True})
    
    except Exception as e:
        app.logger.error(f"Error adding to program list: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_program_list', methods=['GET'])
def get_program_list():
    # Convert program_list to a sorted list for display
    sorted_list = []
    # Sort by number first, then by entry order
    for entry in sorted(program_list, key=lambda x: (int(x['number']) if x['number'].isdigit() else 0, x['id'])):
        xstream_ch = entry.get('xstream')
        xml_ch = entry.get('xml')
        
        sorted_list.append({
            'id': entry['id'],
            'number': entry['number'],
            'xstream_name': xstream_ch.get('name', '') if xstream_ch else '',
            'xstream_epg_id': xstream_ch.get('epg_channel_id', '') if xstream_ch else '',
            'xml_name': xml_ch.get('name', '') if xml_ch else '',
            'xml_epg_id': xml_ch.get('id', '') if xml_ch else '',
            'xml_filename': 'epg.xml' if xml_ch else ''
        })
    
    return jsonify({'success': True, 'program_list': sorted_list})

@app.route('/api/remove_from_program_list', methods=['POST'])
def remove_from_program_list():
    global program_list
    
    try:
        data = request.json
        entry_id = data.get('id')
        
        if not entry_id:
            return jsonify({'success': False, 'error': 'ID erforderlich'}), 400
        
        # Find and remove the entry by ID (modify in-place to persist)
        program_list[:] = [entry for entry in program_list if entry['id'] != entry_id]
        
        return jsonify({'success': True})
    
    except Exception as e:
        app.logger.error(f"Error removing from program list: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auto_match', methods=['POST'])
def auto_match():
    global program_list, next_entry_id
    
    matches = 0
    threshold = 0.8
    
    # Auto-generate numbers starting from 1
    next_number = 1
    
    for xstream_ch in xstream_channels:
        best_match = None
        best_score = 0.0
        
        for xml_ch in xml_channels:
            score = SequenceMatcher(None, xstream_ch.get('name', '').lower(), xml_ch.get('name', '').lower()).ratio()
            if score > best_score and score > threshold:
                best_score = score
                best_match = xml_ch
        
        if best_match:
            # Find next available number
            while any(entry['number'] == str(next_number) for entry in program_list):
                next_number += 1
            
            entry = {
                'id': next_entry_id,
                'number': str(next_number),
                'xstream': xstream_ch,
                'xml': best_match
            }
            program_list.append(entry)
            next_entry_id += 1
            matches += 1
            next_number += 1
    
    return jsonify({
        'success': True,
        'matches': matches
    })

@app.route('/api/list_cache', methods=['GET'])
def list_cache():
    """List all cached EPG files with metadata."""
    metadata = load_cache_metadata()
    files = metadata.get('files', {})
    
    cache_list = []
    for filename, info in files.items():
        cache_list.append({
            'filename': filename,
            'path': info.get('path'),
            'size': info.get('size', 0),
            'created': info.get('created', '')
        })
    
    # Sort by creation date (newest first)
    cache_list.sort(key=lambda x: x['created'], reverse=True)
    
    return jsonify({
        'success': True,
        'files': cache_list
    })

@app.route('/api/load_from_cache', methods=['POST'])
def load_from_cache():
    """Load EPG XML from cache file."""
    global last_xml_raw, last_xml_content, last_xml_is_gz, last_xml_source_name, epg_program_counts, xml_channels
    
    data = request.get_json() or {}
    filename = data.get('filename', '').strip()
    
    if not filename:
        return jsonify({'success': False, 'error': 'Filename erforderlich'}), 400
    
    metadata = load_cache_metadata()
    files = metadata.get('files', {})
    
    if filename not in files:
        return jsonify({'success': False, 'error': 'Datei nicht gefunden'}), 404
    
    file_info = files[filename]
    file_path = file_info.get('path')
    
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'Datei wurde gelöscht'}), 404
    
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Detect if gzipped
        is_gz = filename.endswith('.gz') or file_content[:2] == b'\x1f\x8b'
        
        # Decompress if needed
        if is_gz:
            try:
                content = gzip.decompress(file_content).decode('utf-8')
            except Exception as e:
                return jsonify({'success': False, 'error': f'Dekomprimierung fehlgeschlagen: {str(e)}'}), 500
        else:
            content = file_content.decode('utf-8')
        
        # Store in globals
        last_xml_raw = file_content
        last_xml_content = content
        last_xml_is_gz = is_gz
        last_xml_source_name = filename
        
        # Parse channels
        root = ET.fromstring(content)
        xml_channels = []
        for channel in root.findall('channel'):
            ch_id = channel.get('id', '')
            display_name = channel.find('display-name')
            name = display_name.text if display_name is not None else ''
            xml_channels.append({'id': ch_id, 'name': name})
        
        # Build program counts
        epg_program_counts = build_epg_program_counts(content)
        
        return jsonify({
            'success': True,
            'count': len(xml_channels),
            'channels': xml_channels,
            'channels_with_programs': len([k for k, v in epg_program_counts.items() if v > 0]),
            'total_programmes': sum(epg_program_counts.values())
        })
    
    except Exception as e:
        app.logger.exception(f"Error loading cache file {filename}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/delete_cache_file', methods=['POST'])
def delete_cache_file():
    """Delete a cached EPG file."""
    data = request.get_json() or {}
    filename = data.get('filename', '').strip()
    
    if not filename:
        return jsonify({'success': False, 'error': 'Filename erforderlich'}), 400
    
    metadata = load_cache_metadata()
    files = metadata.get('files', {})
    
    if filename not in files:
        return jsonify({'success': False, 'error': 'Datei nicht gefunden'}), 404
    
    file_info = files[filename]
    file_path = file_info.get('path')
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Remove from metadata
        del metadata['files'][filename]
        save_cache_metadata(metadata)
        
        return jsonify({'success': True})
    
    except Exception as e:
        app.logger.exception(f"Error deleting cache file {filename}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Config nur für Server-Start laden
    startup_config = load_config()
    host = startup_config['server']['host']
    port = startup_config['server']['port']
    app.run(host=host, port=port, debug=True)
