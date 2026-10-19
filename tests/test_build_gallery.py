import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from build_gallery import ROOT, build, match_local_files, render_gallery


class GalleryBuildTests(unittest.TestCase):
    def setUp(self):
        self.records = json.loads((ROOT / 'motionsites_all_prompts.json').read_text())
        self.template = (ROOT / 'motionsites_prompts_gallery.html').read_text()

    def test_embedded_data_preserves_every_existing_record(self):
        rendered = render_gallery(self.template, self.records).decode()
        data = re.search(r'<script id="prompt-data" type="application/json">(.*?)</script>', rendered, re.S)
        self.assertEqual(json.loads(data.group(1)), self.records)

    def test_prompt_text_cannot_end_the_data_element(self):
        record = dict(self.records[0], prompt_text='</script><script>alert("unsafe")</script>&')
        rendered = render_gallery(self.template, [record]).decode()
        data = re.search(r'<script id="prompt-data" type="application/json">(.*?)</script>', rendered, re.S)
        self.assertEqual(json.loads(data.group(1)), [record])
        self.assertNotIn('<', data.group(1))

    def test_duplicate_and_invalid_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            render_gallery(self.template, [self.records[0], self.records[0]])
        with self.assertRaisesRegex(ValueError, 'invalid prompt ID'):
            render_gallery(self.template, [dict(self.records[0], id='../invalid')])

    def test_zip_has_one_root_document_and_rebuilds_reproducibly(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = build(output)
            with zipfile.ZipFile(output / 'motionsites-light-app.zip') as archive:
                self.assertEqual(archive.namelist(), ['index.html'])
                self.assertEqual(archive.read('index.html'), (output / 'index.html').read_bytes())
            self.assertEqual(first, build(output))

    def test_private_build_includes_local_files_without_an_upload_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            videos = root / 'videos'
            videos.mkdir()
            content = b'fixture bytes for packaging, not a playback fixture'
            (videos / 'Interactive Discovery.mp4').write_bytes(content)
            output = root / 'private'
            manifest = build(output, videos)
            self.assertEqual(manifest['local_preview_files'], 1)
            self.assertFalse((output / 'motionsites-light-app.zip').exists())
            page = (output / 'index.html').read_text()
            embedded = re.search(r'<script id="local-preview-data" type="application/json">(.*?)</script>', page, re.S)
            relative = json.loads(embedded.group(1))['interactive-discovery']['path']
            self.assertEqual((output / relative).read_bytes(), content)
            self.assertEqual(len(manifest['missing_local_previews']), 327)
            public = root / 'public'
            public_manifest = build(public)
            self.assertEqual(public_manifest['local_preview_files'], 0)
            self.assertNotIn(relative, (public / 'index.html').read_text())

    def test_private_build_refuses_to_mix_with_an_existing_public_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            videos = root / 'videos'
            videos.mkdir()
            output = root / 'public'
            build(output)
            original = (output / 'index.html').read_bytes()
            with self.assertRaisesRegex(ValueError, 'separate directory'):
                build(output, videos)
            self.assertEqual((output / 'index.html').read_bytes(), original)

    def test_local_file_matching_supports_id_title_and_parent_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'interactive-discovery.mp4').write_bytes(b'1')
            (root / 'Projects Catalog.webm').write_bytes(b'2')
            (root / 'supplement-shop').mkdir()
            (root / 'supplement-shop' / 'video.mp4').write_bytes(b'3')
            (root / 'unknown.mp4').write_bytes(b'4')
            matches, unmatched = match_local_files(root, self.records)
            self.assertEqual(set(matches), {'interactive-discovery', 'projects-catalog', 'supplement-shop'})
            self.assertEqual(unmatched, ['unknown.mp4'])

    def test_multiple_videos_for_one_effect_are_not_silently_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'interactive-discovery.mp4').write_bytes(b'1')
            (root / 'Interactive Discovery.webm').write_bytes(b'2')
            with self.assertRaisesRegex(ValueError, 'Multiple local videos'):
                match_local_files(root, self.records)

    def test_symlinked_local_media_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'private'
            source.mkdir()
            external = root / 'interactive-discovery.mp4'
            external.write_bytes(b'outside')
            (source / external.name).symlink_to(external)
            with self.assertRaisesRegex(ValueError, 'Symlinked or external'):
                match_local_files(source, self.records)

    def test_symlinked_output_cannot_overwrite_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'output'
            output.mkdir()
            external = root / 'external.html'
            external.write_text('keep original')
            (output / 'index.html').symlink_to(external)
            with self.assertRaisesRegex(ValueError, 'must not be a symlink'):
                build(output)
            self.assertEqual(external.read_text(), 'keep original')


if __name__ == '__main__':
    unittest.main()
