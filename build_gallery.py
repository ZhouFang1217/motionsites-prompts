#!/usr/bin/env python3
"""Build a self-contained gallery and a ZIP for static application hosting."""

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_MARKER = '<!-- embedded-prompt-data -->'
LOCAL_MARKER = '<!-- embedded-local-previews -->'
REQUIRED_FIELDS = {'id', 'title', 'category', 'type', 'is_free', 'prompt_text'}
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.m4v', '.ogv', '.ogg'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.avif'}


def normalized_name(value):
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', value.casefold())


def match_local_files(directory, records):
    """Match user-provided filenames exactly; never acquire remote media."""
    directory = directory.resolve(strict=True)
    if not directory.is_dir():
        raise ValueError('The local preview source must be a directory.')
    names = {}
    exact_ids = {record['id'] for record in records}
    for record in records:
        for name in (record['id'], record['title']):
            names.setdefault(normalized_name(name), set()).add(record['id'])
    matches, unmatched = {}, []
    for file in sorted(directory.rglob('*')):
        if file.relative_to(directory).parts[0] == 'posters':
            continue
        if not file.is_file() or file.suffix.lower() not in VIDEO_EXTENSIONS | IMAGE_EXTENSIONS:
            continue
        if file.is_symlink() or directory not in file.resolve().parents:
            raise ValueError('Symlinked or external preview files are not accepted.')
        if file.stem in exact_ids:
            candidates = {file.stem}
        elif file.parent.name in exact_ids:
            candidates = {file.parent.name}
        else:
            candidates = names.get(normalized_name(file.stem), set())
        if not candidates:
            candidates = names.get(normalized_name(file.parent.name), set())
        if len(candidates) != 1:
            unmatched.append(str(file.relative_to(directory)))
            continue
        prompt_id = next(iter(candidates))
        if prompt_id in matches:
            raise ValueError(f'Multiple local videos or images match {prompt_id}; keep one preview per effect.')
        matches[prompt_id] = file
    return matches, unmatched


def encode_json(value):
    encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    for character, escaped in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e')]:
        encoded = encoded.replace(character, escaped)
    return encoded


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


def render_gallery(template, records, local_previews=None):
    validate_records(records)
    if template.count(DATA_MARKER) != 1:
        raise ValueError('The HTML template must contain exactly one data marker.')
    # JSON script tags are inert, but a literal closing tag would end the element.
    encoded = encode_json(records)
    payload = f'<script id="prompt-data" type="application/json">{encoded}</script>'
    if template.count(LOCAL_MARKER) != 1:
        raise ValueError('The HTML template must contain exactly one local preview marker.')
    local_payload = '<script id="local-preview-data" type="application/json">' + encode_json(local_previews or {}) + '</script>'
    library_tag = '<script src="./local_previews.js"></script>'
    if template.count(library_tag) != 1:
        raise ValueError('The HTML template must include the local preview library exactly once.')
    library = (ROOT / 'local_previews.js').read_text(encoding='utf-8')
    rendered = template.replace(DATA_MARKER, payload).replace(LOCAL_MARKER, local_payload)
    return rendered.replace(library_tag, '<script>\n' + library + '\n</script>').encode('utf-8')


def build(output_dir, local_previews=None):
    records = json.loads((ROOT / 'motionsites_all_prompts.json').read_text(encoding='utf-8'))
    template = (ROOT / 'motionsites_prompts_gallery.html').read_text(encoding='utf-8')
    validate_records(records)
    if output_dir.is_symlink():
        raise ValueError('The output directory must not be a symlink.')
    for name in ('index.html', 'manifest.json', 'motionsites-light-app.zip', 'media'):
        if (output_dir / name).is_symlink():
            raise ValueError(f'The output path must not be a symlink: {name}')
    sources, unmatched = match_local_files(local_previews, records) if local_previews else ({}, [])
    if local_previews and (output_dir / 'motionsites-light-app.zip').exists():
        raise ValueError('Use a separate directory for the private gallery; this directory already has a public upload ZIP.')
    local_manifest = {}
    poster_sources = {}
    for prompt_id, file in sources.items():
        checksum = hashlib.sha256()
        with file.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                checksum.update(chunk)
        relative_path = f'media/{prompt_id}-{checksum.hexdigest()[:12]}{file.suffix.lower()}'
        local_manifest[prompt_id] = {
            'path': relative_path,
            'bytes': file.stat().st_size,
            'kind': 'video' if file.suffix.lower() in VIDEO_EXTENSIONS else 'image',
        }
        if file.suffix.lower() in IMAGE_EXTENSIONS:
            local_manifest[prompt_id]['poster'] = relative_path
        elif local_previews:
            poster = local_previews.resolve() / 'posters' / f'{prompt_id}.jpg'
            if poster.exists():
                if poster.is_symlink() or local_previews.resolve() not in poster.resolve().parents:
                    raise ValueError('Symlinked or external preview posters are not accepted.')
                poster_hash = hashlib.sha256(poster.read_bytes()).hexdigest()[:12]
                poster_path = f'media/{prompt_id}-poster-{poster_hash}.jpg'
                local_manifest[prompt_id]['poster'] = poster_path
                poster_sources[poster_path] = poster
    page = render_gallery(template, records, local_manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    for prompt_id, file in sources.items():
        destination = output_dir / local_manifest[prompt_id]['path']
        if destination.is_symlink() or output_dir.resolve() not in destination.resolve().parents:
            raise ValueError('A media output path escapes the output directory.')
        destination.parent.mkdir(exist_ok=True)
        shutil.copyfile(file, destination)
    for relative_path, source in poster_sources.items():
        destination = output_dir / relative_path
        if destination.is_symlink() or output_dir.resolve() not in destination.resolve().parents:
            raise ValueError('A poster output path escapes the output directory.')
        shutil.copyfile(source, destination)
    (output_dir / 'index.html').write_bytes(page)
    archive_path = output_dir / 'motionsites-light-app.zip'
    entry = zipfile.ZipInfo('index.html', date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.external_attr = 0o100644 << 16
    if not local_previews:
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
        'zip_bytes': archive_path.stat().st_size if not local_previews else None,
        'zip_sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest() if not local_previews else None,
        'preview_mode': 'private local files' if local_previews else 'official links and user-imported browser-local videos',
        'mirrored_preview_assets': len(local_manifest),
        'local_preview_files': len(local_manifest),
        'local_preview_videos': sum(item['kind'] == 'video' for item in local_manifest.values()),
        'local_preview_images': sum(item['kind'] == 'image' for item in local_manifest.values()),
        'unmatched_local_files': unmatched,
        'missing_local_previews': [record['id'] for record in records if record['id'] not in local_manifest],
    }
    (output_dir / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Output directory (default: dist, or local_gallery for a private build)')
    parser.add_argument('--local-previews', type=Path, help='Local video/image directory; makes a private gallery without an upload ZIP')
    args = parser.parse_args()
    output = args.output or ROOT / ('local_gallery' if args.local_previews else 'dist')
    manifest = build(output, args.local_previews)
    print(json.dumps({key: value for key, value in manifest.items() if key != 'missing_local_previews'}, ensure_ascii=False, indent=2))
    print(f'Open {output / "index.html"} directly.')
    if args.local_previews:
        print('Private build: local media included; no upload ZIP generated.')


if __name__ == '__main__':
    main()
