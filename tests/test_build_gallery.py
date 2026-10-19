import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from build_gallery import ROOT, build, render_gallery


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


if __name__ == '__main__':
    unittest.main()
