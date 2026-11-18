#!/usr/bin/env python3
"""Prepare auditable agent work packets and validate unsent weekly digests.
No model inference, network, scheduling or Slack sends in this helper.
"""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from collect import atomic_json

PROJECT = Path(__file__).resolve().parents[1]


def prepare(project, collection_log=None):
    config = json.loads((project / 'weekly-config.json').read_text())
    records = [json.loads(s) for s in (project / 'corpus/references.jsonl').read_text().splitlines()]
    run = json.loads(collection_log.read_text()) if collection_log else None
    candidates = []
    for record in records:
        observations = record.get('discovery_observations', [])
        current = [o for o in observations if run and o.get('run_id') == run['run_id']]
        backlog = record.get('screening', {}).get('category') == 'main'
        if run and not current and not backlog:
            continue
        metadata = [o.get('metadata', {}) for o in (current or observations)]
        candidates.append({
            'record_id': record['record_id'], 'title': record.get('title'),
            'primary_url': record.get('primary_url'),
            'abstracts': list(dict.fromkeys(m['abstract'] for m in metadata if m.get('abstract'))),
            'screening': record.get('screening'), 'versions': record.get('versions', []),
            'notes': record.get('notes', []), 'in_current_collection': bool(current),
        })
    return {'created_at': datetime.now(timezone.utc).isoformat(),
            'mode': 'collection_packet' if run else 'offline_snapshot_only',
            'collection': run, 'config': config, 'candidates': candidates,
            'registry_sha256': hashlib.sha256((project / 'corpus/references.jsonl').read_bytes()).hexdigest(),
            'status': 'awaiting_agent_screening', 'delivery': 'not_sent'}


def validate(project, packet, decision):
    """Require explicit disposition of every candidate; never silently truncate."""
    ids = {r['record_id'] for r in packet['candidates']}
    assessments = decision['assessments']
    if len(assessments) != len(ids) or {a['record_id'] for a in assessments} != ids:
        raise ValueError('Every candidate needs exactly one assessment')
    allowed = {'read', 'already_read', 'rejected', 'deferred', 'to_verify'}
    for a in assessments:
        if a.get('decision') not in allowed or not a.get('reason'):
            raise ValueError('Every assessment needs a valid decision and reason')
    if sum(a['decision'] == 'read' for a in assessments) > packet['config']['max_new_full_reads']:
        raise ValueError('Reading cap exceeded')
    chosen = decision['selected']
    if len(chosen) > packet['config']['max_digest_papers'] or len({x['record_id'] for x in chosen}) != len(chosen):
        raise ValueError('Digest cap exceeded or duplicate selected')
    registry = {r['record_id']: r for r in map(json.loads, (project/'corpus/references.jsonl').read_text().splitlines())}
    for item in chosen:
        if item['record_id'] not in ids:
            raise ValueError('Selection not in packet')
        r = registry[item['record_id']]
        if item['note'] not in r.get('notes', []) or not (project/item['note']).is_file():
            raise ValueError('Reading note missing from registry or disk')
        if not item.get('reason'):
            raise ValueError('Selection needs a reason')
        # Non-arXiv sources require equivalent explicit version-level reading evidence.
        matches = [v for v in r.get('versions', []) if v.get('arxiv_id', v.get('version_id')) == item['version']]
        if not any(v.get('reading_status') == 'critical_reading_completed' and v.get('reading_coverage', {}).get('note') == item['note'] for v in matches):
            raise ValueError('Selected version has no completed critical reading')
    draft = project/decision['draft']
    if not draft.is_file() or not draft.read_text().strip():
        raise ValueError('Draft missing or empty')
    return {'status': 'draft_validated_not_sent', 'candidate_count': len(ids),
            'selected_count': len(chosen), 'draft': decision['draft'],
            'draft_sha256': hashlib.sha256(draft.read_bytes()).hexdigest(),
            'scientific_review': 'Agent must still verify claims and citations; structural checks only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'validate'])
    parser.add_argument('--collection-log', type=Path)
    parser.add_argument('--packet', type=Path)
    parser.add_argument('--decision', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(PROJECT, args.collection_log)
    else:
        result = validate(PROJECT, json.loads(args.packet.read_text()), json.loads(args.decision.read_text()))
    if args.output.exists():
        raise SystemExit('Refusing to overwrite existing run artifact')
    atomic_json(args.output, result)
    print(json.dumps({'output': str(args.output), 'status': result['status']}))

if __name__ == '__main__':
    main()
