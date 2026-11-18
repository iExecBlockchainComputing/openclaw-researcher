"""Offline integrity tests; fixtures never enter the project's real corpus."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import subprocess
from pypdf import PdfWriter

spec = importlib.util.spec_from_file_location('reader', Path(__file__).with_name('read_paper.py'))
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class IngestionIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project_patch = patch.object(reader, 'PROJECT', self.root)
        self.project_patch.start()

    def tearDown(self):
        self.project_patch.stop()
        self.temp.cleanup()

    def fixture(self, arxiv_id, pages=12, metadata_id=None):
        folder = self.root / 'corpus/papers' / arxiv_id
        folder.mkdir(parents=True)
        (folder / 'metadata.html').write_text(
            '<meta name="citation_title" content="Fixture paper">'
            '<meta name="citation_author" content="Fixture Author">'
            f'<meta name="citation_arxiv_id" content="{metadata_id or arxiv_id}">')
        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=200, height=200)
        with (folder / 'paper.pdf').open('wb') as f:
            writer.write(f)
        return folder

    def records(self):
        return [json.loads(line) for line in (self.root / 'corpus/references.jsonl').read_text().splitlines()]

    def test_same_version_is_not_duplicated(self):
        self.fixture('2605.24538v1')
        reader.ingest('2605.24538v1', 'pdf')
        with patch.object(reader, 'download', side_effect=AssertionError('Unexpected download')):
            result = reader.ingest('2605.24538v1', 'pdf')
        self.assertEqual(result['status'], 'already_known')
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(len(self.records()[0]['versions']), 1)

    def test_new_version_preserves_old_reading_decision(self):
        self.fixture('2605.24538v1')
        self.fixture('2605.24538v2')
        reader.ingest('2605.24538v1', 'pdf')
        records = self.records()
        records[0]['versions'][0]['reading_status'] = 'targeted_sections_read'
        (self.root / 'corpus/references.jsonl').write_text(json.dumps(records[0]) + '\n')
        reader.ingest('2605.24538v2', 'pdf')
        record = self.records()[0]
        self.assertEqual(len(record['versions']), 2)
        self.assertEqual(record['versions'][0]['reading_status'], 'targeted_sections_read')
        self.assertEqual(record['versions'][1]['reading_status'], 'downloaded_not_yet_read')

    def test_pdf_has_no_ten_page_cap_and_flags_empty_pages(self):
        self.fixture('2605.24538v1', pages=12)
        result = reader.ingest('2605.24538v1', 'pdf')
        self.assertEqual(result['coverage']['pages_attempted'], 12)
        self.assertEqual(result['coverage']['low_text_pages'], list(range(1, 13)))

    def test_metadata_mismatch_does_not_create_record(self):
        self.fixture('2605.24538v1', metadata_id='2412.17114v3')
        with self.assertRaises(ValueError):
            reader.ingest('2605.24538v1', 'pdf')
        self.assertEqual(self.records(), [])
        logs = list((self.root / 'runs').glob('*.json'))
        self.assertTrue(logs)
        log = json.loads(logs[0].read_text())
        self.assertEqual(log['status'], 'failed')
        self.assertFalse(log['source_watermarks_advanced'])

    def test_source_failure_automatically_falls_back_to_pdf(self):
        self.fixture('2605.24538v1')
        error = subprocess.CalledProcessError(1, ['node'], stderr='Source unavailable')
        with patch.object(reader.subprocess, 'run', side_effect=error):
            result = reader.ingest('2605.24538v1', 'auto')
        self.assertEqual(result['method'], 'pdf-text')
        logs = [json.loads(p.read_text()) for p in (self.root / 'runs').glob('*.json')]
        self.assertEqual(logs[0]['errors'][0]['stage'], 'source')
        self.assertEqual(logs[0]['status'], 'success')

    def test_reader_reuses_openalex_origin_record(self):
        self.fixture('2605.24538v1')
        (self.root / 'runs').mkdir()
        record = {'record_id': 'doi:10.1234/example', 'arxiv_id': '2605.24538',
                  'screening': {'category': 'main'}, 'notes': ['kept.md'], 'versions': []}
        (self.root / 'corpus/references.jsonl').write_text(json.dumps(record) + '\n')
        reader.ingest('2605.24538v1', 'pdf')
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(self.records()[0]['record_id'], record['record_id'])
        self.assertEqual(self.records()[0]['screening'], record['screening'])
        self.assertEqual(self.records()[0]['notes'], record['notes'])

    def test_bad_id_rejected_before_download(self):
        for value in ('2605.24538', '../../escapev1', '2605.24538v0'):
            with self.assertRaises(ValueError):
                reader.ingest(value)
        self.assertFalse((self.root / 'corpus').exists())


if __name__ == '__main__':
    unittest.main()
