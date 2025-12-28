import os
import json
import gzip
import io
import xml.etree.ElementTree as ET
from datetime import datetime


# -----------------------------
# General helpers
# -----------------------------

def sanitize_filename(name: str) -> str:
    """Return a safe filename by stripping path traversal and ensuring basename."""
    base = os.path.basename(name or '')
    # very basic sanitization to avoid parent traversal
    base = base.replace('../', '').replace('..', '')
    return base


def detect_gzip_bytes(content: bytes) -> bool:
    """Detect gzip by magic bytes. Caller may also check headers if available."""
    return bool(content) and content[:2] == b'\x1f\x8b'


# -----------------------------
# XML parsing / EPG helpers
# -----------------------------

def parse_xml_channels(xml_text: str):
    """Parse XMLTV text and extract channels as list of dicts {'id','name'}."""
    channels = []
    try:
        root = ET.fromstring(xml_text)
        for channel in root.findall('channel'):
            ch_id = channel.get('id', '')
            display_name = channel.find('display-name')
            name = display_name.text if display_name is not None else ''
            channels.append({'id': ch_id, 'name': name})
    except Exception:
        # Return whatever collected, caller logs if needed
        pass
    return channels


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
    except Exception:
        return {}


# -----------------------------
# Cache metadata helpers
# -----------------------------

def cache_metadata_path(epg_cache_dir: str) -> str:
    return os.path.join(epg_cache_dir, 'metadata.json')


def load_cache_metadata(epg_cache_dir: str):
    """Load cache metadata from JSON file in the given cache dir."""
    metadata_file = cache_metadata_path(epg_cache_dir)
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f) or {}
        except Exception:
            return {}
    return {}


def save_cache_metadata(epg_cache_dir: str, metadata: dict):
    """Save cache metadata to JSON file in the given cache dir."""
    metadata_file = cache_metadata_path(epg_cache_dir)
    try:
        os.makedirs(epg_cache_dir, exist_ok=True)
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception:
        # swallow errors; caller can log
        pass


def add_to_cache(epg_cache_dir: str, filename: str, file_path: str):
    """Register a file in cache metadata under the given cache dir."""
    metadata = load_cache_metadata(epg_cache_dir)
    if 'files' not in metadata:
        metadata['files'] = {}
    metadata['files'][filename] = {
        'path': file_path,
        'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        'created': datetime.now().isoformat()
    }
    save_cache_metadata(epg_cache_dir, metadata)
