"""Offline adversarial checks; fixtures never enter the research corpus."""
import copy
from datetime import date
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('collector', Path(__file__).with_name('collect.py'))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def item(a='2605.24538', d='10.1234/example', title='Decentralized AI governance'):
    return {'arxiv_id': a, 'versioned_id': a + 'v2' if a else None, 'doi': d,
            'title': title, 'authors': ['A. Author'], 'primary_url': 'https://example.org/paper'}


class IdentityTests(unittest.TestCase):
    def test_doi_forms_and_arxiv_doi_normalize(self):
        self.assertEqual(c.doi('https://doi.org/10.1234/EXAMPLE'), '10.1234/example')
        self.assertIn('arxiv:2605.24538', c.identifiers({'doi': '10.48550/arXiv.2605.24538'}))
        self.assertEqual(c.arxiv('https://arxiv.org/pdf/2605.24538v2.pdf')[0], '2605.24538')

    def test_cross_source_match_preserves_decisions_artifacts(self):
        records = [dict(record_id='arxiv:2605.24538', arxiv_id='2605.24538', doi='10.1234/example',
            screening={'category': 'main', 'reason': 'Verified'}, notes=['a.md'],
            versions=[{'arxiv_id': '2605.24538v1', 'reading_status': 'read', 'artifacts': {'source': 'x'}}])]
        before = copy.deepcopy(records[0])
        incoming = item()
        incoming['openalex_ids'] = ['W123']
        for _ in range(2):
            self.assertEqual(c.reconcile(records, incoming, {'snapshot': 'oa.json'})['action'], 'matched')
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['screening'], before['screening'])
        self.assertEqual(records[0]['notes'], before['notes'])
        self.assertEqual(records[0]['versions'][0], before['versions'][0])
        self.assertEqual(records[0]['versions'][1]['reading_status'], 'metadata_only_not_read')
        self.assertEqual(len(records[0]['discovery_observations']), 1)

    def test_openalex_first_then_arxiv_same_doi(self):
        records = []
        c.reconcile(records, {**item(None), 'openalex_ids': ['W123']}, {})
        c.reconcile(records, item(), {'source': 'arxiv'})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['arxiv_id'], '2605.24538')

    def test_title_authors_alone_never_auto_merge(self):
        records = []
        c.reconcile(records, item(), {})
        c.reconcile(records, item('2605.11111', '10.1234/other'), {})
        self.assertEqual(len(records), 2)
        self.assertEqual(len(records[1]['possible_duplicates']), 1)

    def test_ambiguous_bridge_does_not_mutate_records(self):
        records = [{'record_id': 'a', 'doi': '10.1234/example'},
                   {'record_id': 'b', 'arxiv_id': '2605.24538'}]
        before = copy.deepcopy(records)
        self.assertEqual(c.reconcile(records, item(), {})['action'], 'identity_conflict')
        self.assertEqual(records, before)

    def test_shared_doi_distinct_arxiv_is_conflict(self):
        records = []
        c.reconcile(records, item(), {})
        before = copy.deepcopy(records)
        self.assertEqual(c.reconcile(records, item('2605.11111'), {})['action'], 'identity_conflict')
        self.assertEqual(records, before)

    def test_missing_abstract_not_rejected(self):
        body = json.dumps({'meta': {'count': 1}, 'results': [{'id': 'https://openalex.org/W123',
            'title': 'Example', 'type': 'article', 'doi': 'https://doi.org/10.1234/example'}]}).encode()
        _, items = c.parse_openalex(body)
        records = []
        c.reconcile(records, items[0], {})
        self.assertEqual(items[0]['abstract'], '')
        self.assertEqual(records[0]['screening']['category'], 'to verify')


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.qpatch = patch.object(c, 'QUERIES', [('fixture', '"AI" AND "governance"')])
        self.qpatch.start()

    def tearDown(self):
        self.qpatch.stop()
        self.temp.cleanup()

    def fetcher(self, total=1, fail=False):
        def fetch(url, destination):
            if fail:
                raise RuntimeError('fixture network failure')
            page = int(parse_qs(urlparse(url).query)['page'][0])
            body = json.dumps({'meta': {'count': total}, 'results': [{'id': f'https://openalex.org/W{page}',
                'title': 'Paper ' + str(page), 'type': 'article', 'doi': f'10.1234/{page}'}]}).encode()
            destination.write_bytes(body)
            return body
        return fetch

    def run_collection(self, **kwargs):
        return c.collect(project=self.root, sources=('openalex',), end=date(2026, 11, 16), page_size=1, **kwargs)

    def test_successful_pagination_and_replay_idempotence(self):
        with patch.object(c, 'fetch', side_effect=self.fetcher(total=2)):
            first = self.run_collection(max_pages=2)
            second = self.run_collection(max_pages=2)
        self.assertEqual(first['new'], 2)
        self.assertEqual(second['new'], 0)
        self.assertEqual(second['matched'], 2)
        self.assertEqual(first['status'], 'complete')
        state = json.loads((self.root / 'runs/collection-state.json').read_text())
        self.assertEqual(state['openalex']['successful_through'], '2026-11-16')

    def test_capped_or_failed_source_never_advances_boundary(self):
        for fail in (False, True):
            with patch.object(c, 'fetch', side_effect=self.fetcher(total=2, fail=fail)):
                result = self.run_collection(max_pages=1)
            self.assertEqual(result['status'], 'partial')
            self.assertNotIn('openalex', json.loads((self.root / 'runs/collection-state.json').read_text()))

    def test_failure_preserves_previous_boundary(self):
        with patch.object(c, 'fetch', side_effect=self.fetcher()):
            self.run_collection()
        state = (self.root / 'runs/collection-state.json').read_bytes()
        with patch.object(c, 'fetch', side_effect=self.fetcher(fail=True)):
            self.run_collection()
        self.assertEqual((self.root / 'runs/collection-state.json').read_bytes(), state)

    def test_overlap_is_seven_inclusive_days_and_initial_thirty(self):
        end = date(2026, 11, 16)
        self.assertEqual(c.window({}, 'arxiv', end), date(2026, 10, 18))
        self.assertEqual(c.window({'arxiv': {'successful_through': '2026-11-16'}}, 'arxiv', end), date(2026, 11, 10))

    def test_arxiv_error_feed_not_success(self):
        with self.assertRaises(ValueError):
            c.parse_arxiv(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>error</id></entry></feed>')

    def test_repeated_identity_on_changed_page_blocks_boundary(self):
        def fetch(url, destination):
            page = int(parse_qs(urlparse(url).query)['page'][0])
            body = json.dumps({'meta': {'count': 2, 'page': page}, 'results': [
                {'id': 'https://openalex.org/W1', 'title': 'Same work', 'type': 'article'}]}).encode()
            destination.write_bytes(body)
            return body
        with patch.object(c, 'fetch', side_effect=fetch):
            result = self.run_collection(max_pages=2)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['new'], 1)
        self.assertNotIn('openalex', json.loads((self.root / 'runs/collection-state.json').read_text()))

    def test_sources_advance_independently(self):
        def fetch(url, destination):
            if 'arxiv.org' in url:
                raise RuntimeError('arxiv unavailable')
            return self.fetcher()(url, destination)
        with patch.object(c, 'fetch', side_effect=fetch), patch.object(c.time, 'sleep'):
            result = c.collect(project=self.root, end=date(2026, 11, 16), page_size=1)
        self.assertEqual(result['status'], 'partial')
        state = json.loads((self.root / 'runs/collection-state.json').read_text())
        self.assertIn('openalex', state)
        self.assertNotIn('arxiv', state)

    def test_interrupted_request_leaves_trace_without_watermark(self):
        with patch.object(c, 'fetch', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_collection()
        log = json.loads(next((self.root / 'runs').glob('collection-*/run.json')).read_text())
        self.assertEqual(log['status'] if 'status' in log else 'running', 'running')
        self.assertEqual(len(log['sources']['openalex']['queries'][0]['pages']), 1)
        self.assertFalse((self.root / 'runs/collection-state.json').exists())

    def test_current_day_cannot_be_marked_complete(self):
        with self.assertRaises(ValueError):
            c.collect(project=self.root, end=c.datetime.now(c.timezone.utc).date())


if __name__ == '__main__':
    unittest.main()
