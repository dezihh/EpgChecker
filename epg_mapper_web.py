from flask import Flask, render_template, request, jsonify, send_file
import xml.etree.ElementTree as ET
import requests
import json
import io
import gzip
import os
from difflib import SequenceMatcher

app = Flask(__name__)

# Config laden
CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
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

config = load_config()

# In-Memory Storage
xml_channels = []
xstream_channels = []
mappings = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(config)

@app.route('/api/add_history', methods=['POST'])
def add_history():
    global config
    data = request.json
    history_type = data.get('type')  # 'xstream' or 'xml'
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False}), 400
    
    if history_type == 'xstream':
        history_list = config['history']['xstream_urls']
    elif history_type == 'xml':
        history_list = config['history']['xml_urls']
    else:
        return jsonify({'success': False}), 400
    
    # Entferne URL falls bereits vorhanden
    if url in history_list:
        history_list.remove(url)
    
    # Füge am Anfang hinzu
    history_list.insert(0, url)
    
    # Begrenze History
    max_history = config['history']['max_history']
    if len(history_list) > max_history:
        history_list = history_list[:max_history]
    
    if history_type == 'xstream':
        config['history']['xstream_urls'] = history_list
    else:
        config['history']['xml_urls'] = history_list
    
    save_config(config)
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
        
        # Versuche GZ zu entpacken
        if file.filename.endswith('.gz') or file_content[:2] == b'\x1f\x8b':
            try:
                content = gzip.decompress(file_content).decode('utf-8')
                app.logger.info("File decompressed from GZ format")
            except Exception as e:
                app.logger.error(f"GZ decompression failed: {str(e)}")
                return jsonify({'error': f'Fehler beim Entpacken der GZ-Datei: {str(e)}'}), 500
        else:
            content = file_content.decode('utf-8')
        
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
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Prüfe ob Content GZ-komprimiert ist
        content_encoding = response.headers.get('content-encoding', '').lower()
        content_type = response.headers.get('content-type', '').lower()
        
        # Automatische GZ-Erkennung
        if content_encoding == 'gzip' or url.endswith('.gz') or response.content[:2] == b'\x1f\x8b':
            try:
                content = gzip.decompress(response.content).decode('utf-8')
                app.logger.info("URL content decompressed from GZ format")
            except Exception as e:
                app.logger.error(f"GZ decompression failed: {str(e)}")
                return jsonify({'error': f'Fehler beim Entpacken der GZ-Datei: {str(e)}'}), 500
        else:
            content = response.content.decode('utf-8')
        
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
    global xstream_channels, mappings
    
    # Lösche alte Daten und Mappings
    xstream_channels = []
    mappings = {}
    
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
            xstream_channels.append({
                'stream_id': ch.get('stream_id', ''),
                'name': ch.get('name', ''),
                'epg_channel_id': ch.get('epg_channel_id', ''),
                'category_id': ch.get('category_id', '')
            })
        
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
        
        # Add mapping info to xstream channels
        for ch in filtered_xstream:
            ch['mapped_to'] = mappings.get(ch['stream_id'], '')
            if ch['mapped_to']:
                xml_ch = next((x for x in xml_channels if x['id'] == ch['mapped_to']), None)
                ch['mapped_name'] = xml_ch['name'] if xml_ch else ''
            else:
                ch['mapped_name'] = ''
        
        return jsonify({
            'xstream': filtered_xstream,
            'xml': filtered_xml,
            'mappings': mappings
        })
    except Exception as e:
        app.logger.error(f"Error in get_channels: {str(e)}")
        return jsonify({
            'xstream': [],
            'xml': [],
            'mappings': {},
            'error': str(e)
        }), 500

@app.route('/api/map', methods=['POST'])
def create_mapping():
    global mappings
    
    data = request.json
    stream_id = data.get('stream_id')
    xml_id = data.get('xml_id')
    
    if not stream_id or not xml_id:
        return jsonify({'error': 'Stream ID und XML ID erforderlich'}), 400
    
    mappings[stream_id] = xml_id
    
    return jsonify({'success': True, 'mappings': mappings})

@app.route('/api/unmap', methods=['POST'])
def remove_mapping():
    global mappings
    
    data = request.json
    stream_id = data.get('stream_id')
    
    if stream_id in mappings:
        del mappings[stream_id]
    
    return jsonify({'success': True, 'mappings': mappings})

@app.route('/api/auto_match', methods=['POST'])
def auto_match():
    global mappings
    
    matches = 0
    threshold = 0.8
    
    for xstream_ch in xstream_channels:
        best_match = None
        best_score = 0.0
        
        for xml_ch in xml_channels:
            score = SequenceMatcher(None, xstream_ch['name'].lower(), xml_ch['name'].lower()).ratio()
            if score > best_score and score > threshold:
                best_score = score
                best_match = xml_ch
        
        if best_match:
            mappings[xstream_ch['stream_id']] = best_match['id']
            matches += 1
    
    return jsonify({
        'success': True,
        'matches': matches,
        'mappings': mappings
    })

@app.route('/api/export/<format>')
def export_mappings(format):
    if not mappings:
        return jsonify({'error': 'Keine Zuordnungen vorhanden'}), 400
    
    if format == 'txt':
        output = io.StringIO()
        output.write("# IPTV EPG Mapping\n")
        output.write("# Format: XStream_Stream_ID | XStream_Name | XML_EPG_ID | XML_Name\n\n")
        
        for stream_id, xml_id in mappings.items():
            xstream_ch = next((x for x in xstream_channels if x['stream_id'] == stream_id), None)
            xml_ch = next((x for x in xml_channels if x['id'] == xml_id), None)
            
            if xstream_ch and xml_ch:
                output.write(f"{stream_id} | {xstream_ch['name']} | {xml_id} | {xml_ch['name']}\n")
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/plain',
            as_attachment=True,
            download_name='epg_mapping.txt'
        )
    
    elif format == 'json':
        export_data = []
        for stream_id, xml_id in mappings.items():
            xstream_ch = next((x for x in xstream_channels if x['stream_id'] == stream_id), None)
            xml_ch = next((x for x in xml_channels if x['id'] == xml_id), None)
            
            if xstream_ch and xml_ch:
                export_data.append({
                    'xstream_stream_id': stream_id,
                    'xstream_name': xstream_ch['name'],
                    'xstream_epg_id': xstream_ch['epg_channel_id'],
                    'xml_epg_id': xml_id,
                    'xml_name': xml_ch['name']
                })
        
        return send_file(
            io.BytesIO(json.dumps(export_data, indent=2, ensure_ascii=False).encode('utf-8')),
            mimetype='application/json',
            as_attachment=True,
            download_name='epg_mapping.json'
        )
    
    elif format == 'csv':
        output = io.StringIO()
        output.write("XStream_Stream_ID;XStream_Name;XStream_EPG_ID;XML_EPG_ID;XML_Name\n")
        
        for stream_id, xml_id in mappings.items():
            xstream_ch = next((x for x in xstream_channels if x['stream_id'] == stream_id), None)
            xml_ch = next((x for x in xml_channels if x['id'] == xml_id), None)
            
            if xstream_ch and xml_ch:
                output.write(f"{stream_id};{xstream_ch['name']};{xstream_ch['epg_channel_id']};{xml_id};{xml_ch['name']}\n")
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='epg_mapping.csv'
        )
    
    return jsonify({'error': 'Unbekanntes Format'}), 400

if __name__ == '__main__':
    host = config['server']['host']
    port = config['server']['port']
    app.run(host=host, port=port, debug=True)
