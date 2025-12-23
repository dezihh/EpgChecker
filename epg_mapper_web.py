from flask import Flask, render_template, request, jsonify
import xml.etree.ElementTree as ET
import requests
import json
import gzip
import os
from difflib import SequenceMatcher

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
    global xml_channels
    
    if 'file' not in request.files:
        return jsonify({'error': 'Keine Datei hochgeladen'}), 400
    
    file = request.files['file']
    
    try:
        # Prüfe ob Datei komprimiert ist
        file_content = file.read()
        
        # Versuche GZ zu entpacken nur wenn es wirklich GZ ist
        is_gzipped = (file.filename.endswith('.gz') or file_content[:2] == b'\x1f\x8b')
        
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
        
        return jsonify({
            'success': True,
            'count': len(xml_channels),
            'channels': xml_channels
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/load_xml_url', methods=['POST'])
def load_xml_url():
    global xml_channels
    
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
    global xstream_channels, program_list, next_entry_id
    
    # Lösche alte Daten und Programmliste
    xstream_channels = []
    program_list = []
    next_entry_id = 1
    
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
        
        # Find and remove the entry by ID
        program_list = [entry for entry in program_list if entry['id'] != entry_id]
        
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

if __name__ == '__main__':
    # Config nur für Server-Start laden
    startup_config = load_config()
    host = startup_config['server']['host']
    port = startup_config['server']['port']
    app.run(host=host, port=port, debug=True)
