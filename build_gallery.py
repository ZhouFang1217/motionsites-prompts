#!/usr/bin/env python3
"""Build a self-contained gallery and a ZIP for static application hosting."""

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_MARKER = '<!-- embedded-prompt-data -->'
REQUIRED_FIELDS = {'id', 'title', 'category', 'type', 'is_free', 'prompt_text'}


def validate_records(records):
    if not isinstance(records, list) or not records:
        raise ValueError('The catalog must be a non-empty JSON array.')
    ids = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not REQUIRED_FIELDS <= record.keys():
            raise ValueError(f'Record {index} is missing required fields.')
        prompt_id = record['id']
        if not isinstance(prompt_id, str) or not re.fullmatch(r'[a-z0-9-]+', prompt_id):
            raise ValueError(f'Record {index} has an invalid prompt ID.')
        if prompt_id in ids:
            raise ValueError(f'Duplicate prompt ID: {prompt_id}')
        ids.add(prompt_id)
        if record.get('platform') not in {'website', 'app'}:
            raise ValueError(f'Unknown platform for prompt {prompt_id}.')
        if not isinstance(record['prompt_text'], str) or not isinstance(record['title'], str):
            raise ValueError(f'Invalid title or prompt text for {prompt_id}.')


def render_gallery(template, records):
    validate_records(records)
    if template.count(DATA_MARKER) != 1:
        raise ValueError('The HTML template must contain exactly one data marker.')
    encoded = json.dumps(records, ensure_ascii=False, separators=(',', ':'))
    # JSON script tags are inert, but a literal closing tag would end the element.
    for character, escaped in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e')]:
        encoded = encoded.replace(character, escaped)
    payload = f'<script id="prompt-data" type="application/json">{encoded}</script>'
    return template.replace(DATA_MARKER, payload).encode('utf-8')


def build(output_dir):
    records = json.loads((ROOT / 'motionsites_all_prompts.json').read_text(encoding='utf-8'))
    template = (ROOT / 'motionsites_prompts_gallery.html').read_text(encoding='utf-8')
    page = render_gallery(template, records)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'index.html').write_bytes(page)
    archive_path = output_dir / 'motionsites-light-app.zip'
    entry = zipfile.ZipInfo('index.html', date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.external_attr = 0o100644 << 16
    with zipfile.ZipFile(archive_path, 'w', compresslevel=9) as archive:
        archive.writestr(entry, page)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.namelist() != ['index.html'] or archive.testzip() is not None:
            raise ValueError('The static hosting archive failed validation.')
        if archive.read('index.html') != page:
            raise ValueError('The archive differs from the generated page.')
    manifest = {
        'records': len(records),
        'official_preview_links': len(records),
        'html_bytes': len(page),
        'html_sha256': hashlib.sha256(page).hexdigest(),
        'zip_bytes': archive_path.stat().st_size,
        'zip_sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        'preview_mode': 'external official links; network required for previews',
        'mirrored_preview_assets': 0,
    }
    (output_dir / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist', help='Output directory')
    args = parser.parse_args()
    print(json.dumps(build(args.output), ensure_ascii=False, indent=2))
    print(f'Open {args.output / "index.html"} directly, or upload the generated ZIP.')


if __name__ == '__main__':
    main()
