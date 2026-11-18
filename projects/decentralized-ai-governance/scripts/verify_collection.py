#!/usr/bin/env python3
"""Read-only checks of collection snapshots and the shared registry."""
import hashlib
import json
from pathlib import Path
from collect import PROJECT, identifiers, parse_arxiv, parse_openalex


def verify(project=PROJECT):
    records = [json.loads(x) for x in (project / 'corpus/references.jsonl').read_text().splitlines() if x.strip()]
    keys = [r['record_id'] for r in records]
    assert len(keys) == len(set(keys)), 'Duplicate logical record IDs'
    anchors = {}
    for r in records:
        for identity in identifiers(r):
            assert identity not in anchors or anchors[identity] == r['record_id'], f'Unresolved shared identity {identity}'
            anchors[identity] = r['record_id']
        versions = [v['arxiv_id'] for v in r['versions']]
        assert len(versions) == len(set(versions)), 'Duplicate paper versions'
        for note in r.get('notes', []):
            assert (project / note).is_file(), f'Missing note {note}'
    snapshots = observations = 0
    for logpath in sorted((project / 'runs').glob('collection-*/run.json')):
        log = json.loads(logpath.read_text())
        for source, source_log in log['sources'].items():
            if source_log['status'] == 'complete':
                assert all(q['status'] == 'complete' for q in source_log['queries'])
            for query in source_log['queries']:
                for page in query['pages']:
                    if 'snapshot' not in page:
                        continue
                    raw = (project / page['snapshot']).read_bytes()
                    assert hashlib.sha256(raw).hexdigest() == page['sha256'], 'Snapshot hash mismatch'
                    total, items = (parse_arxiv if source == 'arxiv' else parse_openalex)(raw)
                    assert total == page['total_reported'] and len(items) == page['returned']
                    snapshots += 1
                    observations += len(items)
                    # A metadata replay must resolve to an already registered identity.
                    for item in items:
                        matches = {anchors[i] for i in identifiers(item) if i in anchors}
                        assert len(matches) == 1, f'Missing/ambiguous collected identity: {item["title"]}'
    background = next(r for r in records if r['record_id'] == 'arxiv:2605.24538')
    assert background['screening']['category'] == 'main'
    assert background['notes'] == ['corpus/notes/2605.24538v1.md']
    version = next(v for v in background['versions'] if v['arxiv_id'] == '2605.24538v1')
    assert version['reading_status'] == 'targeted_critical_reading_completed'
    for artifact in version['artifacts'].values():
        for path, digest in artifact['sha256'].items():
            assert hashlib.sha256((project / path).read_bytes()).hexdigest() == digest, 'Existing artifact changed'
    return {'status': 'passed', 'records': len(records), 'snapshots_verified': snapshots,
            'observations_replayed_without_new_identity': observations,
            'cross_source_records': sum(len({o['source'] for o in r.get('discovery_observations', [])}) > 1 for r in records),
            'existing_reader_note_status_and_hashes': 'preserved'}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
