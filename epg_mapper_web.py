<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPTV EPG Mapper</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .subtitle {
            opacity: 0.9;
            font-size: 1.1em;
        }
        
        .content {
            padding: 30px;
        }
        
        .section {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
        
        .section-title {
            font-size: 1.3em;
            color: #667eea;
            margin-bottom: 15px;
            font-weight: 600;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 15px;
        }
        
        input[type="text"],
        input[type="password"],
        input[type="file"] {
            padding: 10px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1em;
            flex: 1;
            min-width: 200px;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        button {
            padding: 10px 25px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        button:active {
            transform: translateY(0);
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .btn-secondary {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }
        
        .channels-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 20px;
        }
        
        .channel-list {
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
        }
        
        .list-header {
            background: #667eea;
            color: white;
            padding: 15px;
            font-weight: 600;
            font-size: 1.1em;
        }
        
        .list-content {
            height: 500px;
            overflow-y: auto;
        }
        
        .channel-item {
            padding: 12px 15px;
            border-bottom: 1px solid #f0f0f0;
            cursor: pointer;
            transition: background 0.2s;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .channel-item:hover {
            background: #f8f9fa;
        }
        
        .channel-item.selected {
            background: #e3f2fd;
            border-left: 4px solid #667eea;
        }
        
        .channel-item.mapped {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
        }
        
        .channel-name {
            font-weight: 500;
            flex: 1;
        }
        
        .channel-id {
            font-size: 0.85em;
            color: #666;
            margin-left: 10px;
        }
        
        .mapped-info {
            font-size: 0.8em;
            color: #4caf50;
            margin-top: 3px;
        }
        
        .controls {
            display: flex;
            gap: 10px;
            justify-content: center;
            margin: 20px 0;
            flex-wrap: wrap;
        }
        
        .status-bar {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            text-align: center;
            font-weight: 500;
        }
        
        .status-bar.success {
            background: #e8f5e9;
            color: #2e7d32;
        }
        
        .status-bar.error {
            background: #ffebee;
            color: #c62828;
        }
        
        .stats {
            display: flex;
            gap: 20px;
            justify-content: center;
            margin: 20px 0;
            flex-wrap: wrap;
        }
        
        .stat-card {
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            min-width: 150px;
            text-align: center;
        }
        
        .stat-number {
            font-size: 2.5em;
            font-weight: 700;
            color: #667eea;
        }
        
        .stat-label {
            color: #666;
            margin-top: 5px;
        }
        
        @media (max-width: 1024px) {
            .channels-container {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 IPTV EPG Mapper</h1>
            <p class="subtitle">Ordne deine IPTV-Sender den EPG-Daten zu</p>
        </div>
        
        <div class="content">
            <!-- XStream API Section -->
            <div class="section">
                <div class="section-title">🌐 XStream API Zugangsdaten</div>
                <div class="input-group">
                    <input type="text" id="xstream-url" placeholder="Server:Port (z.B. http://192.168.1.100:8080)" style="flex: 2;">
                    <input type="text" id="xstream-user" placeholder="Username">
                    <input type="password" id="xstream-pass" placeholder="Password">
                    <button onclick="loadXStream()">XStream Laden</button>
                </div>
                <div style="margin-top: 10px; font-size: 0.9em; color: #666;">
                    ℹ️ Nur Server-URL mit Port angeben (z.B. http://server:80) - ohne /player_api.php
                </div>
            </div>
            
            <!-- XML Upload Section -->
            <div class="section">
                <div class="section-title">📄 XML EPG Datei</div>
                <div class="input-group">
                    <input type="text" id="xml-url" placeholder="XML EPG URL (auch .gz möglich)" style="flex: 2;">
                    <button onclick="loadXMLFromURL()">Von URL laden</button>
                </div>
                <div class="input-group" style="margin-top: 10px;">
                    <input type="file" id="xml-file" accept=".xml,.gz">
                    <button onclick="uploadXML()">Datei hochladen</button>
                </div>
                <div style="margin-top: 10px; font-size: 0.9em; color: #666;">
                    ℹ️ Unterstützt XML und GZ-komprimierte Dateien
                </div>
            </div>
            
            <!-- Stats -->
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number" id="xstream-count">0</div>
                    <div class="stat-label">XStream Sender</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="xml-count">0</div>
                    <div class="stat-label">XML Sender</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="mapping-count">0</div>
                    <div class="stat-label">Zuordnungen</div>
                </div>
            </div>
            
            <!-- Search -->
            <div class="section">
                <div class="input-group">
                    <input type="text" id="search" placeholder="🔍 Sender suchen..." oninput="loadChannels()">
                    <button class="btn-success" onclick="autoMatch()">✨ Auto-Match</button>
                </div>
            </div>
            
            <!-- Channel Lists -->
            <div class="channels-container">
                <div class="channel-list">
                    <div class="list-header">XStream Sender</div>
                    <div class="list-content" id="xstream-list"></div>
                </div>
                
                <div class="channel-list">
                    <div class="list-header">XML EPG Sender</div>
                    <div class="list-content" id="xml-list"></div>
                </div>
            </div>
            
            <!-- Controls -->
            <div class="controls">
                <button onclick="mapChannels()">➡️ Zuordnen</button>
                <button onclick="unmapChannel()">⬅️ Zuordnung entfernen</button>
            </div>
            
            <!-- Export -->
            <div class="section">
                <div class="section-title">💾 Export</div>
                <div class="controls">
                    <button onclick="exportMapping('txt')">Export als TXT</button>
                    <button onclick="exportMapping('json')">Export als JSON</button>
                    <button onclick="exportMapping('csv')">Export als CSV</button>
                </div>
            </div>
            
            <!-- Status Bar -->
            <div class="status-bar" id="status">Bereit</div>
        </div>
    </div>
    
    <script>
        let selectedXStream = null;
        let selectedXML = null;
        let allXStreamChannels = [];
        let allXMLChannels = [];
        const ITEMS_PER_PAGE = 100;
        let currentXStreamPage = 1;
        let currentXMLPage = 1;
        let appConfig = {};
        
        function setStatus(message, type = '') {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = 'status-bar ' + type;
        }
        
        // Config laden beim Start
        async function loadConfig() {
            try {
                const response = await fetch('/api/config');
                
                if (!response.ok) {
                    console.error('Config fetch failed:', response.status);
                    return;
                }
                
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    console.error('Config response is not JSON');
                    return;
                }
                
                appConfig = await response.json();
                
                // Felder mit Config vorausfüllen
                if (appConfig.xstream && appConfig.xstream.url) {
                    document.getElementById('xstream-url').value = appConfig.xstream.url;
                }
                if (appConfig.xstream && appConfig.xstream.username) {
                    document.getElementById('xstream-user').value = appConfig.xstream.username;
                }
                if (appConfig.xstream && appConfig.xstream.password) {
                    document.getElementById('xstream-pass').value = appConfig.xstream.password;
                }
                if (appConfig.xml_epg && appConfig.xml_epg.url) {
                    document.getElementById('xml-url').value = appConfig.xml_epg.url;
                }
                
                // History Dropdowns erstellen
                setupHistoryDropdowns();
            } catch (error) {
                console.error('Fehler beim Laden der Config:', error);
                // Nicht kritisch - App funktioniert auch ohne Config
            }
        }
        
        function setupHistoryDropdowns() {
            // XStream History
            const xstreamUrlInput = document.getElementById('xstream-url');
            const xstreamDatalist = document.createElement('datalist');
            xstreamDatalist.id = 'xstream-history';
            
            if (appConfig.history && appConfig.history.xstream_urls) {
                appConfig.history.xstream_urls.forEach(url => {
                    const option = document.createElement('option');
                    option.value = url;
                    xstreamDatalist.appendChild(option);
                });
            }
            
            xstreamUrlInput.setAttribute('list', 'xstream-history');
            document.body.appendChild(xstreamDatalist);
            
            // XML History
            const xmlUrlInput = document.getElementById('xml-url');
            const xmlDatalist = document.createElement('datalist');
            xmlDatalist.id = 'xml-history';
            
            if (appConfig.history && appConfig.history.xml_urls) {
                appConfig.history.xml_urls.forEach(url => {
                    const option = document.createElement('option');
                    option.value = url;
                    xmlDatalist.appendChild(option);
                });
            }
            
            xmlUrlInput.setAttribute('list', 'xml-history');
            document.body.appendChild(xmlDatalist);
        }
        
        async function addToHistory(type, url) {
            try {
                await fetch('/api/add_history', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({type, url})
                });
            } catch (error) {
                console.error('Fehler beim Speichern der History:', error);
            }
        }
        
        async function uploadXML() {
            const fileInput = document.getElementById('xml-file');
            const file = fileInput.files[0];
            
            if (!file) {
                setStatus('Bitte eine Datei auswählen', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                setStatus('Lade XML...', '');
                const response = await fetch('/api/upload_xml', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.error) {
                    setStatus('Fehler: ' + data.error, 'error');
                    return;
                }
                
                setStatus(`XML geladen: ${data.count} Sender`, 'success');
                document.getElementById('xml-count').textContent = data.count;
                loadChannels();
            } catch (error) {
                setStatus('Fehler beim Hochladen: ' + error.message, 'error');
            }
        }
        
        async function loadXMLFromURL() {
            const url = document.getElementById('xml-url').value.trim();
            
            if (!url) {
                setStatus('Bitte eine URL eingeben', 'error');
                return;
            }
            
            try {
                setStatus('Lade XML von URL...', '');
                
                // Zur History hinzufügen
                await addToHistory('xml', url);
                
                const response = await fetch('/api/load_xml_url', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url})
                });
                
                const data = await response.json();
                
                if (data.error) {
                    setStatus('Fehler: ' + data.error, 'error');
                    return;
                }
                
                setStatus(`XML von URL geladen: ${data.count} Sender`, 'success');
                document.getElementById('xml-count').textContent = data.count;
                
                // Config neu laden um History zu aktualisieren
                await loadConfig();
                
                loadChannels();
            } catch (error) {
                setStatus('Fehler beim Laden: ' + error.message, 'error');
            }
        }
        
        async function loadXStream() {
            const url = document.getElementById('xstream-url').value.trim();
            const username = document.getElementById('xstream-user').value.trim();
            const password = document.getElementById('xstream-pass').value.trim();
            
            if (!url || !username || !password) {
                setStatus('Bitte alle Felder ausfüllen', 'error');
                return;
            }
            
            try {
                setStatus('Lade XStream Daten...', '');
                
                // Zur History hinzufügen
                await addToHistory('xstream', url);
                
                const response = await fetch('/api/load_xstream', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url, username, password})
                });
                
                const data = await response.json();
                
                if (data.error) {
                    setStatus('Fehler: ' + data.error, 'error');
                    return;
                }
                
                setStatus(`XStream geladen: ${data.count} Sender`, 'success');
                document.getElementById('xstream-count').textContent = data.count;
                
                // Config neu laden um History zu aktualisieren
                await loadConfig();
                
                loadChannels();
            } catch (error) {
                setStatus('Fehler beim Laden: ' + error.message, 'error');
            }
        }
        
        async function loadChannels() {
            const search = document.getElementById('search').value;
            
            try {
                setStatus('Lade Kanäle...', '');
                const response = await fetch(`/api/get_channels?search=${encodeURIComponent(search)}`);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('Response is not JSON:', text.substring(0, 500));
                    setStatus('Fehler: Server antwortet nicht mit JSON', 'error');
                    return;
                }
                
                const data = await response.json();
                
                if (data.error) {
                    setStatus('Fehler: ' + data.error, 'error');
                    return;
                }
                
                allXStreamChannels = data.xstream || [];
                allXMLChannels = data.xml || [];
                
                currentXStreamPage = 1;
                currentXMLPage = 1;
                
                renderXStreamList();
                renderXMLList();
                
                document.getElementById('mapping-count').textContent = Object.keys(data.mappings || {}).length;
                setStatus('Bereit', '');
            } catch (error) {
                console.error('Fehler beim Laden:', error);
                setStatus('Fehler beim Laden der Kanäle: ' + error.message, 'error');
            }
        }
        
        function renderXStreamList() {
            const list = document.getElementById('xstream-list');
            const start = (currentXStreamPage - 1) * ITEMS_PER_PAGE;
            const end = start + ITEMS_PER_PAGE;
            const pageChannels = allXStreamChannels.slice(start, end);
            
            list.innerHTML = '';
            
            // Pagination Info
            const totalPages = Math.ceil(allXStreamChannels.length / ITEMS_PER_PAGE);
            if (totalPages > 1) {
                const paginationInfo = document.createElement('div');
                paginationInfo.style.cssText = 'padding: 10px; background: #f0f0f0; text-align: center; font-weight: bold; position: sticky; top: 0; z-index: 10;';
                paginationInfo.innerHTML = `
                    <button onclick="changeXStreamPage(-1)" ${currentXStreamPage === 1 ? 'disabled' : ''}>◀</button>
                    Seite ${currentXStreamPage} von ${totalPages} (${allXStreamChannels.length} Sender)
                    <button onclick="changeXStreamPage(1)" ${currentXStreamPage === totalPages ? 'disabled' : ''}>▶</button>
                `;
                list.appendChild(paginationInfo);
            }
            
            pageChannels.forEach(ch => {
                const item = document.createElement('div');
                item.className = 'channel-item' + (ch.mapped_to ? ' mapped' : '');
                item.onclick = () => selectXStream(ch.stream_id);
                
                const content = `
                    <div>
                        <div class="channel-name">${ch.name}</div>
                        ${ch.epg_channel_id ? `<div class="channel-id">EPG: ${ch.epg_channel_id}</div>` : ''}
                        ${ch.mapped_name ? `<div class="mapped-info">→ ${ch.mapped_name}</div>` : ''}
                    </div>
                `;
                
                item.innerHTML = content;
                item.dataset.streamId = ch.stream_id;
                list.appendChild(item);
            });
        }
        
        function renderXMLList() {
            const list = document.getElementById('xml-list');
            const start = (currentXMLPage - 1) * ITEMS_PER_PAGE;
            const end = start + ITEMS_PER_PAGE;
            const pageChannels = allXMLChannels.slice(start, end);
            
            list.innerHTML = '';
            
            // Pagination Info
            const totalPages = Math.ceil(allXMLChannels.length / ITEMS_PER_PAGE);
            if (totalPages > 1) {
                const paginationInfo = document.createElement('div');
                paginationInfo.style.cssText = 'padding: 10px; background: #f0f0f0; text-align: center; font-weight: bold; position: sticky; top: 0; z-index: 10;';
                paginationInfo.innerHTML = `
                    <button onclick="changeXMLPage(-1)" ${currentXMLPage === 1 ? 'disabled' : ''}>◀</button>
                    Seite ${currentXMLPage} von ${totalPages} (${allXMLChannels.length} Sender)
                    <button onclick="changeXMLPage(1)" ${currentXMLPage === totalPages ? 'disabled' : ''}>▶</button>
                `;
                list.appendChild(paginationInfo);
            }
            
            pageChannels.forEach(ch => {
                const item = document.createElement('div');
                item.className = 'channel-item';
                item.onclick = () => selectXML(ch.id);
                
                const content = `
                    <div>
                        <div class="channel-name">${ch.name}</div>
                        <div class="channel-id">${ch.id}</div>
                    </div>
                `;
                
                item.innerHTML = content;
                item.dataset.xmlId = ch.id;
                list.appendChild(item);
            });
        }
        
        function changeXStreamPage(direction) {
            const totalPages = Math.ceil(allXStreamChannels.length / ITEMS_PER_PAGE);
            currentXStreamPage = Math.max(1, Math.min(totalPages, currentXStreamPage + direction));
            renderXStreamList();
        }
        
        function changeXMLPage(direction) {
            const totalPages = Math.ceil(allXMLChannels.length / ITEMS_PER_PAGE);
            currentXMLPage = Math.max(1, Math.min(totalPages, currentXMLPage + direction));
            renderXMLList();
        }
        
        function selectXStream(streamId) {
            document.querySelectorAll('#xstream-list .channel-item').forEach(el => {
                el.classList.remove('selected');
            });
            
            const item = document.querySelector(`#xstream-list .channel-item[data-stream-id="${streamId}"]`);
            if (item) {
                item.classList.add('selected');
                selectedXStream = streamId;
            }
        }
        
        function selectXML(xmlId) {
            document.querySelectorAll('#xml-list .channel-item').forEach(el => {
                el.classList.remove('selected');
            });
            
            const item = document.querySelector(`#xml-list .channel-item[data-xml-id="${xmlId}"]`);
            if (item) {
                item.classList.add('selected');
                selectedXML = xmlId;
            }
        }
        
        async function mapChannels() {
            if (!selectedXStream || !selectedXML) {
                setStatus('Bitte je einen Sender auswählen', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/map', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        stream_id: selectedXStream,
                        xml_id: selectedXML
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    setStatus('Zuordnung erstellt', 'success');
                    loadChannels();
                    selectedXStream = null;
                    selectedXML = null;
                }
            } catch (error) {
                setStatus('Fehler beim Zuordnen: ' + error.message, 'error');
            }
        }
        
        async function unmapChannel() {
            if (!selectedXStream) {
                setStatus('Bitte einen XStream-Sender auswählen', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/unmap', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({stream_id: selectedXStream})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    setStatus('Zuordnung entfernt', 'success');
                    loadChannels();
                    selectedXStream = null;
                }
            } catch (error) {
                setStatus('Fehler: ' + error.message, 'error');
            }
        }
        
        async function autoMatch() {
            try {
                setStatus('Suche automatische Übereinstimmungen...', '');
                const response = await fetch('/api/auto_match', {method: 'POST'});
                const data = await response.json();
                
                if (data.success) {
                    setStatus(`Auto-Match: ${data.matches} Zuordnungen gefunden`, 'success');
                    loadChannels();
                }
            } catch (error) {
                setStatus('Fehler beim Auto-Match: ' + error.message, 'error');
            }
        }
        
        function exportMapping(format) {
            window.location.href = `/api/export/${format}`;
            setStatus(`Export als ${format.toUpperCase()} gestartet`, 'success');
        }
        
        // Initial load - nur Config laden, keine Channels
        loadConfig();
    </script>
</body>
</html>
