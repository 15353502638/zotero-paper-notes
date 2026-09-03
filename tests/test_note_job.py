"""Offline checks with synthetic notes and images; no Zotero connection."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'note_job', ROOT / 'skills/zotero-paper-notes/scripts/note_job.py')
note_job = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(note_job)


class NoteJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.original = '<div><h2 style="color:blue">自选栏目</h2><p>个人批注</p></div>'
        self.snap = {
            'parent': {'data': {'key': 'PARENT01', 'itemType': 'journalArticle'}},
            'note': {'data': {'key': 'NOTETEST', 'itemType': 'note',
                             'parentItem': 'PARENT01', 'note': self.original},
                     'library': {'type': 'user'}}}
        self.write('snapshot.json', self.snap)
        self.html = self.work / 'note.html'
        self.html.write_text(self.original.replace('</div>', '{{FIG1}}</div>'), encoding='utf-8')
        Image.new('RGB', (80, 40), (30, 100, 150)).save(self.work / 'figure.png')
        self.write('images.json', [{'marker': '{{FIG1}}', 'file': 'figure.png',
                                   'caption': 'Synthetic test image', 'pdfKey': 'PDFTEST1',
                                   'page': 2, 'width': 80}])
        self.args = SimpleNamespace(snapshot=self.work / 'snapshot.json', html=self.html,
                                    images=self.work / 'images.json', out=self.work / 'job.json')

    def write(self, name, obj):
        (self.work / name).write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')

    def prepare(self):
        with contextlib.redirect_stdout(io.StringIO()):
            note_job.prepare(self.args)
        return note_job.read_json(self.args.out)

    def test_prepares_custom_template_without_changing_it(self):
        job = self.prepare()
        self.assertEqual(job['expectedHTML'], self.original)
        self.assertEqual(job['html'], self.html.read_text(encoding='utf-8'))
        image = job['images'][0]
        self.assertEqual(image['height'], 40)
        self.assertEqual(image['sha256'], hashlib.sha256((self.work / 'figure.png').read_bytes()).hexdigest())
        runner = self.args.out.with_suffix('.run.js').read_text(encoding='utf-8')
        self.assertNotIn('__JOB_FILE_JSON__', runner)

    def test_rejects_wrong_note_parent(self):
        self.snap['note']['data']['parentItem'] = 'OTHER001'
        self.write('snapshot.json', self.snap)
        with self.assertRaisesRegex(ValueError, 'relationship'):
            self.prepare()

    def test_rejects_unfilled_template(self):
        self.html.write_text('<p>{{UNFILLED}}</p>{{FIG1}}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Unfilled'):
            self.prepare()

    def test_rejects_repeated_image_marker(self):
        self.html.write_text('<p>{{FIG1}}{{FIG1}}</p>', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unique'):
            self.prepare()

    def test_preserves_existing_job(self):
        self.prepare()
        before = self.args.out.read_bytes()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.prepare()
        self.assertEqual(self.args.out.read_bytes(), before)

    def test_canonical_comparison_preserves_content_and_style(self):
        self.assertEqual(note_job.canonical('<p><a href="x">link</a></p>'),
                         note_job.canonical('<p><a rel="noopener" href="x">link</a></p>'))
        self.assertNotEqual(note_job.canonical('<h2 style="color:blue">text</h2>'),
                            note_job.canonical('<h2 style="color:red">text</h2>'))
        self.assertNotEqual(note_job.canonical('<p>before</p>'), note_job.canonical('<p>after</p>'))

    def test_verifies_stored_image_and_detects_changed_bytes(self):
        job = self.prepare()
        html = '<div><p>结果</p><img data-attachment-key="IMAGE001"></div>'
        self.write('job.result.json', {'id': job['id'], 'stage': 'complete', 'html': html,
                                      'images': [{'key': 'IMAGE001'}]})
        items = {
            'NOTETEST': {'data': {'parentItem': 'PARENT01', 'note': html}},
            'IMAGE001': {'data': {'parentItem': 'NOTETEST', 'contentType': 'image/png'}}}
        file_url = (self.work / 'figure.png').as_uri().encode()
        def response(*args, **kwargs):
            return io.BytesIO(file_url)
        with patch.object(note_job, 'fetch_item', side_effect=items.__getitem__), \
             patch.object(note_job.urllib.request, 'urlopen', side_effect=response), \
             contextlib.redirect_stdout(io.StringIO()):
            note_job.verify(SimpleNamespace(job=self.args.out))
            (self.work / 'figure.png').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'differs'):
                note_job.verify(SimpleNamespace(job=self.args.out))


if __name__ == '__main__':
    unittest.main()
