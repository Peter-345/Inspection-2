#!/usr/bin/env python3
"""
HTML Report Generator für Audit-Berichte
Erstellt einen responsiven HTML-Bericht aus CSV-Daten und zugehörigen Fotos
"""

import csv
import os
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import sys


def read_csv_data(csv_path: str) -> Tuple[Dict, List[Dict]]:
    """
    Liest die CSV-Datei und gibt Metadaten und Items zurück

    Returns:
        Tuple[Dict, List[Dict]]: (metadata, items)
    """
    metadata = {}
    items = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)

        # Lese die ersten Zeilen als Metadata (bis zur Header-Zeile)
        for row in reader:
            if not row:
                continue

            # Prüfe ob wir bei der Header-Zeile angekommen sind
            if row[0] == 'ID':
                # Ab hier kommen die strukturierten Daten
                header = row
                break

            # Speichere Metadata
            if len(row) >= 2:
                key = row[0]
                value = row[1]
                metadata[key] = value

        # Lese die Items
        for row in reader:
            if not row or not row[0]:
                continue

            item = {}
            for i, col in enumerate(header):
                if i < len(row):
                    item[col] = row[i]
                else:
                    item[col] = ''

            items.append(item)

    return metadata, items


def format_timestamp(timestamp_str: str) -> str:
    """Formatiert einen Unix-Timestamp zu einem lesbaren Datum"""
    try:
        timestamp = int(timestamp_str)
        return datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M')
    except (ValueError, OSError):
        return timestamp_str


def get_image_base64(image_path: str) -> str:
    """Konvertiert ein Bild zu Base64 für Inline-HTML"""
    try:
        with open(image_path, 'rb') as f:
            data = f.read()
            ext = Path(image_path).suffix.lower()
            mime_type = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png'
            return f"data:{mime_type};base64,{base64.b64encode(data).decode()}"
    except Exception as e:
        print(f"Warnung: Konnte Bild nicht laden: {image_path} - {e}")
        return ""


def parse_primary_value(primary: str) -> Tuple[str, str]:
    """
    Parst den Primary-Wert (Format: "ID|Wert")

    Returns:
        Tuple[str, str]: (option_id, display_value)
    """
    if '|' in primary:
        parts = primary.split('|', 1)
        return parts[0], parts[1]
    return '', primary


def get_color_class(value: str) -> str:
    """Gibt die CSS-Klasse basierend auf dem Wert zurück"""
    if 'OK' in value:
        return 'status-ok'
    elif 'Non-compliant' in value or '不合格' in value:
        return 'status-noncompliant'
    elif 'Info' in value or '说明' in value:
        return 'status-info'
    elif 'n. a.' in value or 'n.a.' in value:
        return 'status-na'
    return ''


def get_status_type(value: str) -> str:
    """Gibt den Status-Typ für Filter zurück"""
    if 'OK' in value:
        return 'ok'
    elif 'Non-compliant' in value or '不合格' in value:
        return 'noncompliant'
    elif 'Info' in value or '说明' in value:
        return 'info'
    elif 'n. a.' in value or 'n.a.' in value:
        return 'na'
    return 'other'


def format_text_with_chinese_red(text: str) -> str:
    """
    Formatiert Text so, dass chinesische Zeichen rot dargestellt werden
    """
    import re

    # Regex für chinesische Zeichen inkl. Zahlen und NUR chinesische Satzzeichen
    chinese_pattern = re.compile(r'[\u4e00-\u9fff\d，。、：；！？（）【】《》""''・\s]+')

    # Ersetze chinesische Zeichen mit rot formatiertem Span
    def replace_chinese(match):
        matched_text = match.group(0)
        # Nur rot färben, wenn mindestens ein chinesisches Zeichen vorhanden ist
        if re.search(r'[\u4e00-\u9fff]', matched_text):
            return f'<span style="color: #dc3545; font-weight: 600;">{matched_text}</span>'
        else:
            return matched_text  # Unverändert zurückgeben (keine chinesischen Zeichen)

    return chinese_pattern.sub(replace_chinese, text)


def remove_gps_coordinates(text: str) -> str:
    """
    Entfernt GPS-Koordinaten aus dem Text
    """
    import re

    # Entferne Zeilen, die nur Koordinaten enthalten (z.B. "30.989;121.216" oder mit Komma)
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        # Skip Zeilen mit Semikolon-getrennten Koordinaten
        if ';' in line and line.replace(';', '').replace('.', '').replace('-', '').replace(' ', '').isdigit():
            continue
        # Skip Zeilen mit Koordinaten in Klammern
        if re.match(r'^\s*\([\d\.\,\s\-]+\)\s*$', line):
            continue
        # Entferne Koordinaten in Klammern am Ende einer Zeile
        line = re.sub(r'\s*\([\d\.\,\s\-]+\)\s*$', '', line)

        if line:  # Nur nicht-leere Zeilen
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def is_item_answered(item: Dict) -> bool:
    """
    Prüft, ob ein Item beantwortet wurde

    Returns:
        bool: True wenn beantwortet, False wenn leer
    """
    # Ein Item gilt als beantwortet, wenn mindestens eines vorhanden ist:
    # - Primary (Antwort)
    # - Secondary (zusätzliche Info)
    # - Note (Notiz)
    # - Media (Fotos)
    return bool(item.get('Primary') or item.get('Secondary') or item.get('Note') or item.get('Media'))


def organize_items_by_sections(items: List[Dict]) -> List[Dict]:
    """
    Organisiert Items nach Sections

    Returns:
        List[Dict]: Liste von Sections mit ihren zugehörigen Items
    """
    sections = []
    current_section = None

    for item in items:
        if item['Type'] == 'section':
            if current_section:
                sections.append(current_section)
            current_section = {
                'id': item['ID'],
                'label': item['Label'],
                'items': []
            }
        elif current_section:
            current_section['items'].append(item)

    # Füge die letzte Section hinzu
    if current_section:
        sections.append(current_section)

    return sections


def get_machine_designation(items: List[Dict]) -> str:
    """
    Extrahiert die Machine designation aus den Items
    """
    for item in items:
        if 'Machine designation' in item.get('Label', '') or '机器名称' in item.get('Label', ''):
            return item.get('Primary', 'Audit Bericht')
    return 'Audit Bericht'


def generate_html_report(csv_path: str, output_path: str):
    """
    Generiert den HTML-Bericht
    """
    print("Lese CSV-Datei...")
    metadata, items = read_csv_data(csv_path)

    print("Organisiere Daten...")
    sections = organize_items_by_sections(items)

    # Lade Logo
    logo_path = '/Users/volkerallmendinger/Downloads/download-4.png'
    logo_base64 = ''
    if os.path.exists(logo_path):
        logo_base64 = get_image_base64(logo_path)

    # Bestimme den Bildordner
    csv_dir = os.path.dirname(csv_path)

    print("Generiere HTML...")

    # HTML-Template
    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{metadata.get('audit_title', 'Audit Bericht')}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
            padding-left: 20px;
            transition: padding-left 0.3s ease;
        }}

        body.toc-open {{
            padding-left: 370px;
        }}

        .toc-sidebar {{
            position: fixed;
            left: -350px;
            top: 0;
            width: 350px;
            height: 100vh;
            background: white;
            box-shadow: 2px 0 10px rgba(0,0,0,0.1);
            overflow-y: auto;
            z-index: 1000;
            transition: left 0.3s ease;
            padding: 20px;
        }}

        .toc-sidebar.open {{
            left: 0;
        }}

        .toc-toggle {{
            position: fixed;
            left: 20px;
            top: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 25px;
            cursor: pointer;
            z-index: 1001;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .toc-toggle:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.5);
        }}

        .toc-toggle::before {{
            content: "☰";
            font-size: 1.2em;
        }}

        body.toc-open .toc-toggle {{
            left: 370px;
        }}

        body.toc-open .toc-toggle::before {{
            content: "✕";
        }}

        .toc-header {{
            font-size: 1.3em;
            font-weight: 700;
            color: #2c3e50;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #3498db;
        }}

        .toc-section {{
            margin-bottom: 20px;
        }}

        .toc-section-title {{
            font-weight: 600;
            color: #2c3e50;
            font-size: 0.95em;
            margin-bottom: 8px;
            padding: 8px 12px;
            background: #f8f9fa;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.2s;
        }}

        .toc-section-title:hover {{
            background: #e9ecef;
        }}

        .toc-items {{
            margin-left: 15px;
            margin-top: 5px;
        }}

        .toc-item {{
            display: flex;
            align-items: center;
            padding: 6px 10px;
            margin: 3px 0;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.9em;
        }}

        .toc-item:hover {{
            background: #f8f9fa;
            transform: translateX(5px);
        }}

        .toc-item-status {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: 600;
            margin-right: 8px;
            min-width: 50px;
            text-align: center;
            flex-shrink: 0;
        }}

        .toc-item-status.ok {{
            background: #a8d5ba;
            color: #0d3d1a;
        }}

        .toc-item-status.noncompliant {{
            background: #f0b3b8;
            color: #5a0f15;
        }}

        .toc-item-status.info {{
            background: #ffd966;
            color: #6b5200;
        }}

        .toc-item-status.na {{
            background: #c8ccd0;
            color: #2d3236;
        }}

        .toc-item-status.other {{
            background: #e9ecef;
            color: #495057;
        }}

        .toc-item-label {{
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-radius: 8px;
        }}

        .header {{
            border-bottom: 3px solid #2c3e50;
            padding-bottom: 30px;
            margin-bottom: 40px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 30px;
        }}

        .header-logo {{
            max-width: 400px;
            height: auto;
        }}

        .header h1 {{
            color: #2c3e50;
            font-size: 2.5em;
            margin: 0;
            flex: 1;
        }}

        .metadata {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 12px;
            margin-bottom: 25px;
        }}

        .metadata-item {{
            padding: 10px 12px;
            background: #f8f9fa;
            border-left: 3px solid #3498db;
            border-radius: 3px;
        }}

        .metadata-label {{
            font-weight: 600;
            color: #555;
            font-size: 0.8em;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}

        .metadata-value {{
            font-size: 0.95em;
            color: #2c3e50;
            margin-top: 3px;
            white-space: pre-wrap;
        }}

        .filter-container {{
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin: 30px 0;
            border-left: 4px solid #3498db;
        }}

        .filter-title {{
            font-size: 1.3em;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
        }}

        .filter-title::before {{
            content: "🔍";
            margin-right: 10px;
            font-size: 1.2em;
        }}

        .filter-options {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }}

        .filter-option {{
            display: flex;
            align-items: center;
            padding: 12px 20px;
            border: 2px solid #e9ecef;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.2s;
            background: white;
            user-select: none;
        }}

        .filter-option:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }}

        .filter-option input[type="checkbox"] {{
            width: 20px;
            height: 20px;
            cursor: pointer;
            margin-right: 10px;
        }}

        .filter-option.active {{
            border-width: 2px;
        }}

        .filter-option.filter-ok {{
            border-color: #28a745;
        }}

        .filter-option.filter-ok.active {{
            background: #a8d5ba;
        }}

        .filter-option.filter-noncompliant {{
            border-color: #dc3545;
        }}

        .filter-option.filter-noncompliant.active {{
            background: #f0b3b8;
        }}

        .filter-option.filter-info {{
            border-color: #ffc107;
        }}

        .filter-option.filter-info.active {{
            background: #ffd966;
        }}

        .filter-option.filter-na {{
            border-color: #6c757d;
        }}

        .filter-option.filter-na.active {{
            background: #c8ccd0;
        }}

        .filter-option label {{
            cursor: pointer;
            font-weight: 600;
            font-size: 1em;
        }}

        .filter-stats {{
            margin-top: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 6px;
            font-size: 0.95em;
            color: #6c757d;
        }}

        .section.hidden {{
            display: none;
        }}

        .item.hidden {{
            display: none;
        }}

        /* Print Styles */
        @media print {{
            .filter-container,
            .lightbox,
            .toc-sidebar,
            .toc-toggle {{
                display: none !important;
            }}

            body {{
                background: white;
                padding: 0 !important;
                padding-left: 0 !important;
            }}

            .container {{
                box-shadow: none;
                padding: 20px;
                max-width: 100%;
            }}

            .section {{
                page-break-inside: avoid;
                break-inside: avoid;
            }}

            .item {{
                page-break-inside: avoid;
                break-inside: avoid;
                margin-bottom: 15px;
            }}

            /* Seitenumbruch nach Items mit vielen Fotos (>= 5) */
            .item.page-break-after {{
                page-break-after: always;
                break-after: page;
            }}

            /* Seitenumbruch nach jedem 2. Item mit wenigen Fotos */
            .item.page-break-after-small {{
                page-break-after: always;
                break-after: page;
            }}

            .image-container {{
                page-break-inside: avoid;
                break-inside: avoid;
            }}

            .images-grid {{
                page-break-inside: avoid;
                break-inside: avoid;
            }}

            .section-header {{
                page-break-after: avoid;
                break-after: avoid;
            }}

            .item-label {{
                page-break-after: avoid;
                break-after: avoid;
            }}
        }}

        .section {{
            margin: 50px 0;
            page-break-inside: avoid;
        }}

        .section-header {{
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 20px 25px;
            border-radius: 8px 8px 0 0;
            font-size: 1.5em;
            font-weight: 600;
        }}

        .section-content {{
            border: 1px solid #ddd;
            border-top: none;
            border-radius: 0 0 8px 8px;
            padding: 20px;
            background: #f8f9fa;
        }}

        /* Spezielle kompakte Darstellung für Title Page */
        .section.title-page .section-content {{
            padding: 12px;
        }}

        .section.title-page .item {{
            padding: 8px 12px;
            margin-bottom: 8px;
            display: grid;
            grid-template-columns: 200px 1fr;
            gap: 15px;
            align-items: start;
        }}

        .section.title-page .item-label {{
            font-size: 0.9em;
            margin-bottom: 0;
            font-weight: 600;
            color: #555;
            background: #dde1e7;
            padding: 8px 12px;
            border-radius: 4px;
            border-left: 3px solid #3498db;
        }}

        .section.title-page .item-value,
        .section.title-page .item-notes {{
            margin: 0;
            padding: 8px 12px;
            background: none;
            border: none;
            font-size: 0.9em;
            grid-column: 2;
        }}

        .section.title-page .images-grid {{
            grid-column: 1 / -1;
            margin-top: 8px;
        }}

        .item {{
            padding: 30px;
            margin-bottom: 20px;
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: all 0.2s;
        }}

        .item:last-child {{
            margin-bottom: 0;
        }}

        .item:hover {{
            background: #fefefe;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            border-color: #3498db;
            transform: translateY(-2px);
        }}

        .item-label {{
            font-size: 1.1em;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 15px;
            line-height: 1.4;
            background: #dde1e7;
            padding: 12px 15px;
            border-radius: 6px;
            border-left: 4px solid #3498db;
        }}

        .item-value {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            margin: 10px 0;
        }}

        .status-ok {{
            background: #a8d5ba;
            color: #0d3d1a;
            border: 1px solid #85c49a;
        }}

        .status-noncompliant {{
            background: #f0b3b8;
            color: #5a0f15;
            border: 1px solid #e89399;
        }}

        .status-info {{
            background: #ffd966;
            color: #6b5200;
            border: 1px solid #ffc933;
        }}

        .status-na {{
            background: #c8ccd0;
            color: #2d3236;
            border: 1px solid #adb2b8;
        }}

        .item-notes {{
            background: #fff9e6;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
            white-space: pre-wrap;
        }}

        .images-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 15px;
        }}

        .image-container {{
            position: relative;
            overflow: hidden;
            transition: transform 0.2s;
        }}

        .image-container:hover {{
            transform: scale(1.02);
        }}

        .image-container img {{
            width: 100%;
            height: 400px;
            object-fit: contain;
            display: block;
            cursor: pointer;
        }}

        /* Lightbox für Bildansicht */
        .lightbox {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }}

        .lightbox.active {{
            display: flex;
        }}

        .lightbox img {{
            max-width: 95%;
            max-height: 95%;
            object-fit: contain;
            border-radius: 4px;
        }}

        .lightbox-close {{
            position: absolute;
            top: 20px;
            right: 40px;
            color: white;
            font-size: 40px;
            cursor: pointer;
            font-weight: 300;
            transition: color 0.2s;
        }}

        .lightbox-close:hover {{
            color: #f39c12;
        }}

        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}

            .container {{
                padding: 20px;
            }}

            .header {{
                flex-direction: column;
                align-items: flex-start;
            }}

            .header h1 {{
                font-size: 1.8em;
            }}

            .header-logo {{
                max-width: 250px;
            }}

            .metadata {{
                grid-template-columns: 1fr;
            }}

            .images-grid {{
                grid-template-columns: repeat(2, 1fr);
                gap: 8px;
            }}

            .image-container img {{
                height: 300px;
            }}

            .score-value {{
                font-size: 2em;
            }}
        }}


        @media print {{
            body {{
                background: white;
                padding: 0;
            }}

            .container {{
                box-shadow: none;
                padding: 20px;
            }}

            .item {{
                page-break-inside: avoid;
            }}

            .lightbox {{
                display: none !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Inspektionsbericht</h1>
            {f'<img src="{logo_base64}" alt="Umenge Machine Inspections" class="header-logo">' if logo_base64 else ''}
        </div>

        <div class="filter-container">
            <div class="filter-title">Status Filter</div>
            <div class="filter-options">
                <div class="filter-option filter-ok active" onclick="toggleFilter(this, 'ok')">
                    <input type="checkbox" id="filter-ok" checked onchange="event.stopPropagation(); toggleFilter(this.parentElement, 'ok')">
                    <label for="filter-ok">✓ OK</label>
                </div>
                <div class="filter-option filter-noncompliant active" onclick="toggleFilter(this, 'noncompliant')">
                    <input type="checkbox" id="filter-noncompliant" checked onchange="event.stopPropagation(); toggleFilter(this.parentElement, 'noncompliant')">
                    <label for="filter-noncompliant">✗ Non-compliant</label>
                </div>
                <div class="filter-option filter-info active" onclick="toggleFilter(this, 'info')">
                    <input type="checkbox" id="filter-info" checked onchange="event.stopPropagation(); toggleFilter(this.parentElement, 'info')">
                    <label for="filter-info">ⓘ Info</label>
                </div>
                <div class="filter-option filter-na active" onclick="toggleFilter(this, 'na')">
                    <input type="checkbox" id="filter-na" checked onchange="event.stopPropagation(); toggleFilter(this.parentElement, 'na')">
                    <label for="filter-na">— n.a.</label>
                </div>
            </div>
            <div class="filter-stats" id="filter-stats">
                Zeige alle Items
            </div>
        </div>
"""

    # Generiere Inhaltsverzeichnis
    toc_html = """
    <!-- Toggle Button für Inhaltsverzeichnis -->
    <button class="toc-toggle" onclick="toggleTOC()">Inhalt</button>

    <!-- Sidebar Inhaltsverzeichnis -->
    <div class="toc-sidebar" id="toc-sidebar">
        <div class="toc-header">Inhaltsverzeichnis</div>
"""

    for section in sections:
        # Prüfe ob Section beantwortete Items hat
        answered_items = [item for item in section['items']
                         if item['Type'] != 'category' and is_item_answered(item)]

        if not answered_items:
            continue

        section_id = section['id'].replace('-', '_')
        toc_html += f"""
        <div class="toc-section">
            <div class="toc-section-title" onclick="scrollToSection('{section_id}')">{section['label'][:50]}{'...' if len(section['label']) > 50 else ''}</div>
            <div class="toc-items">
"""

        for item in section['items']:
            if item['Type'] == 'category' or not is_item_answered(item):
                continue

            # Bestimme Status
            status_type = 'other'
            status_label = '—'
            if item['Primary']:
                option_id, display_value = parse_primary_value(item['Primary'])
                status_type = get_status_type(display_value)
                if status_type == 'ok':
                    status_label = 'OK'
                elif status_type == 'noncompliant':
                    status_label = 'NC'
                elif status_type == 'info':
                    status_label = 'Info'
                elif status_type == 'na':
                    status_label = 'n.a.'

            item_id = item['ID'].replace('-', '_')
            # Kürze Label für TOC
            item_label = item['Label'][:60] + ('...' if len(item['Label']) > 60 else '')

            toc_html += f"""
                <div class="toc-item" onclick="scrollToItem('{item_id}')">
                    <span class="toc-item-status {status_type}">{status_label}</span>
                    <span class="toc-item-label" title="{item['Label']}">{item_label}</span>
                </div>
"""

        toc_html += """
            </div>
        </div>
"""

    toc_html += """
    </div>
"""

    html += toc_html

    # Füge Sections hinzu
    for section in sections:
        # Prüfe ob Section beantwortete Items hat
        answered_items = [item for item in section['items']
                         if item['Type'] != 'category' and is_item_answered(item)]

        # Skip Section wenn keine beantworteten Items vorhanden sind
        if not answered_items:
            continue

        section_id = section['id'].replace('-', '_')
        # Prüfe ob es die Title Page Section ist
        is_title_page = 'title' in section['label'].lower() or '标题页' in section['label']
        title_page_class = ' title-page' if is_title_page else ''

        html += f"""
        <div class="section{title_page_class}" id="{section_id}">
            <div class="section-header">{section['label']}</div>
            <div class="section-content">
"""

        # Sortiere Items der Title Page: Machine designation zuerst
        items_to_display = section['items']
        if is_title_page:
            machine_items = [item for item in items_to_display if 'machine designation' in item.get('Label', '').lower() or '机器名称' in item.get('Label', '')]
            other_items = [item for item in items_to_display if item not in machine_items]
            items_to_display = machine_items + other_items

        # Zähler für kleine Items (< 5 Fotos) für intelligente Seitenumbrüche
        small_items_count = 0

        for item in items_to_display:
            # Skip category items (diese sind nur Gruppierungen)
            if item['Type'] == 'category':
                continue

            # Skip nicht beantwortete Fragen
            if not is_item_answered(item):
                continue

            # Skip Location-Felder
            if 'location' in item.get('Label', '').lower() or '地点' in item.get('Label', ''):
                continue

            # Bestimme den Status für Filter
            status_type = 'other'
            if item['Primary']:
                option_id, display_value = parse_primary_value(item['Primary'])
                status_type = get_status_type(display_value)

            # Zähle Anzahl der Fotos
            photo_count = 0
            if item['Media']:
                image_ids = [img_id.strip() for img_id in item['Media'].split(';') if img_id.strip()]
                photo_count = len(image_ids)

            # Bestimme ob Seitenumbruch nötig ist
            page_break_class = ''
            if photo_count >= 5:
                # Viele Fotos: Seitenumbruch direkt nach diesem Item
                page_break_class = 'page-break-after'
                small_items_count = 0  # Reset counter
            else:
                # Wenige Fotos: Zähle und füge nach jedem 2. kleinen Item einen Umbruch ein
                small_items_count += 1
                if small_items_count >= 2:
                    page_break_class = 'page-break-after-small'
                    small_items_count = 0  # Reset counter

            item_id = item['ID'].replace('-', '_')
            html += f"""
                <div class="item {page_break_class}" data-status="{status_type}" id="{item_id}">
                    <div class="item-label">{item['Label']}</div>
"""

            # Zeige Primary Value (Antwort/Auswahl)
            if item['Primary']:
                option_id, display_value = parse_primary_value(item['Primary'])

                # Formatiere Timestamps (wenn es nur Zahlen sind und wahrscheinlich ein Timestamp ist)
                if display_value.strip().isdigit() and len(display_value.strip()) == 10:
                    display_value = format_timestamp(display_value)

                # Entferne GPS-Koordinaten aus Location-Feldern
                if 'location' in item['Label'].lower() or '地点' in item['Label']:
                    display_value = remove_gps_coordinates(display_value)

                color_class = get_color_class(display_value)
                html += f'                    <div class="item-value {color_class}">{display_value}</div>\n'

            # Zeige Notes (mit chinesischem Text in rot, außer bei Location)
            # Nur anzeigen wenn vorhanden und unterschiedlich von Secondary
            if item['Note']:
                is_location = 'location' in item['Label'].lower() or '地点' in item['Label']

                # Entferne GPS-Koordinaten aus Location-Feldern
                if is_location:
                    formatted_note = remove_gps_coordinates(item["Note"])
                else:
                    formatted_note = format_text_with_chinese_red(item["Note"])

                html += f'                    <div class="item-notes">{formatted_note}</div>\n'
            elif item['Secondary'] and item['Secondary'] != item['Primary']:
                # Zeige Secondary nur wenn keine Note vorhanden ist
                is_location = 'location' in item['Label'].lower() or '地点' in item['Label']

                # Entferne GPS-Koordinaten aus Location-Feldern
                if is_location:
                    formatted_secondary = remove_gps_coordinates(item["Secondary"])
                else:
                    formatted_secondary = format_text_with_chinese_red(item["Secondary"])

                html += f'                    <div class="item-notes">{formatted_secondary}</div>\n'

            # Zeige Bilder
            if item['Media']:
                image_ids = [img_id.strip() for img_id in item['Media'].split(';') if img_id.strip()]

                if image_ids:
                    html += '                    <div class="images-grid">\n'

                    for img_id in image_ids:
                        # Suche nach dem Bild (kann .jpg oder .png sein)
                        img_path = None
                        for ext in ['.jpg', '.jpeg', '.png']:
                            test_path = os.path.join(csv_dir, img_id + ext)
                            if os.path.exists(test_path):
                                img_path = test_path
                                break

                        if img_path:
                            img_base64 = get_image_base64(img_path)
                            if img_base64:
                                html += f'''                        <div class="image-container">
                            <img src="{img_base64}" alt="Bild {img_id}" onclick="openLightbox(this.src)">
                        </div>
'''

                    html += '                    </div>\n'

            html += """                </div>
"""

        html += """            </div>
        </div>
"""

    # Schließe HTML
    html += """    </div>

    <!-- Lightbox für Bildansicht -->
    <div class="lightbox" id="lightbox" onclick="closeLightbox()">
        <span class="lightbox-close">&times;</span>
        <img id="lightbox-img" src="" alt="Vergrößertes Bild">
    </div>

    <script>
        function openLightbox(src) {
            document.getElementById('lightbox').classList.add('active');
            document.getElementById('lightbox-img').src = src;
        }

        function closeLightbox() {
            document.getElementById('lightbox').classList.remove('active');
        }

        // ESC-Taste zum Schließen
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeLightbox();
            }
        });

        // Filter-Funktionalität
        let activeFilters = new Set(['ok', 'noncompliant', 'info', 'na', 'other']);

        function toggleFilter(element, filterType) {
            const checkbox = element.querySelector('input[type="checkbox"]');

            // Toggle checkbox wenn auf div geklickt wurde
            if (event.target === element) {
                checkbox.checked = !checkbox.checked;
            }

            // Toggle active class
            if (checkbox.checked) {
                element.classList.add('active');
                activeFilters.add(filterType);
            } else {
                element.classList.remove('active');
                activeFilters.delete(filterType);
            }

            applyFilters();
        }

        function applyFilters() {
            let visibleCount = 0;
            let totalCount = 0;

            // Durchlaufe alle Items
            document.querySelectorAll('.item').forEach(item => {
                totalCount++;
                const status = item.getAttribute('data-status');

                if (activeFilters.has(status)) {
                    item.classList.remove('hidden');
                    visibleCount++;
                } else {
                    item.classList.add('hidden');
                }
            });

            // Verstecke Sections ohne sichtbare Items
            document.querySelectorAll('.section').forEach(section => {
                const visibleItems = section.querySelectorAll('.item:not(.hidden)');
                if (visibleItems.length === 0) {
                    section.classList.add('hidden');
                } else {
                    section.classList.remove('hidden');
                }
            });

            // Update Statistik
            updateFilterStats(visibleCount, totalCount);
        }

        function updateFilterStats(visible, total) {
            const statsEl = document.getElementById('filter-stats');
            if (visible === total) {
                statsEl.textContent = `Zeige alle ${total} Items`;
            } else {
                statsEl.textContent = `Zeige ${visible} von ${total} Items`;
            }
        }

        // Initialisiere Filter-Statistik beim Laden
        document.addEventListener('DOMContentLoaded', function() {
            applyFilters();
        });

        // Inhaltsverzeichnis Toggle
        function toggleTOC() {
            const sidebar = document.getElementById('toc-sidebar');
            const body = document.body;

            sidebar.classList.toggle('open');
            body.classList.toggle('toc-open');
        }

        // Scroll zu Section
        function scrollToSection(sectionId) {
            const element = document.getElementById(sectionId);
            if (element) {
                element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                // Highlight effect
                element.style.transition = 'background 0.5s';
                element.style.background = '#fff3cd';
                setTimeout(() => {
                    element.style.background = '';
                }, 1500);
            }
        }

        // Scroll zu Item
        function scrollToItem(itemId) {
            const element = document.getElementById(itemId);
            if (element) {
                element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                // Highlight effect
                element.style.transition = 'background 0.5s, transform 0.3s';
                element.style.background = '#fff3cd';
                element.style.transform = 'scale(1.02)';
                setTimeout(() => {
                    element.style.background = '';
                    element.style.transform = '';
                }, 1500);
            }
        }

        // Schließe TOC bei ESC-Taste
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                const sidebar = document.getElementById('toc-sidebar');
                const body = document.body;
                if (sidebar.classList.contains('open')) {
                    sidebar.classList.remove('open');
                    body.classList.remove('toc-open');
                }
            }
        });
    </script>
</body>
</html>
"""

    # Schreibe HTML-Datei
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✓ HTML-Bericht erfolgreich erstellt: {output_path}")


def find_audit_folders(script_dir: str) -> List[str]:
    """
    Findet alle Audit-Ordner im Script-Verzeichnis
    """
    audit_folders = []

    for item in os.listdir(script_dir):
        item_path = os.path.join(script_dir, item)
        # Prüfe ob es ein Verzeichnis ist und mit "audit_" beginnt
        if os.path.isdir(item_path) and item.startswith('audit_'):
            audit_folders.append(item_path)

    return audit_folders


def find_csv_in_folder(folder_path: str) -> str:
    """
    Findet die CSV-Datei in einem Ordner
    """
    for file in os.listdir(folder_path):
        if file.endswith('.csv'):
            return os.path.join(folder_path, file)
    return None


def main():
    """Hauptfunktion"""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 60)
    print("HTML Audit-Bericht Generator")
    print("=" * 60)

    # Finde alle Audit-Ordner
    audit_folders = find_audit_folders(script_dir)

    if not audit_folders:
        print("FEHLER: Keine Audit-Ordner gefunden!")
        print(f"Suche nach Ordnern mit 'audit_' Präfix in: {script_dir}")
        sys.exit(1)

    print(f"Gefundene Audit-Ordner: {len(audit_folders)}")
    print()

    # Verarbeite jeden Audit-Ordner
    for audit_folder in audit_folders:
        folder_name = os.path.basename(audit_folder)
        print(f"Verarbeite: {folder_name}")

        # Finde CSV-Datei
        csv_file = find_csv_in_folder(audit_folder)

        if not csv_file:
            print(f"  ⚠ Keine CSV-Datei gefunden in {folder_name}")
            continue

        # Erstelle Output-Dateinamen
        csv_basename = os.path.splitext(os.path.basename(csv_file))[0]
        output_file = os.path.join(script_dir, f"{csv_basename}_bericht.html")

        print(f"  CSV: {os.path.basename(csv_file)}")
        print(f"  Output: {os.path.basename(output_file)}")

        try:
            # Generiere Bericht
            generate_html_report(csv_file, output_file)
            print(f"  ✓ Erfolgreich erstellt!")
        except Exception as e:
            print(f"  ✗ Fehler: {e}")

        print()

    print("=" * 60)
    print("Fertig! Alle Berichte wurden erstellt.")
    print("=" * 60)


if __name__ == '__main__':
    main()
