#!/usr/bin/env python3
"""Bounded, manual arXiv/OpenAlex discovery. No scheduling, accounts or delivery."""
import argparse
from datetime import date, datetime, timedelta, timezone
import difflib
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unicodedata
from urllib.parse import urlencode, unquote
import xml.etree.ElementTree as ET

PROJECT = Path(__file__).resolve().parents[1]
NS = {'a': 'http://www.w3.org/2005/Atom', 'o': 'http://a9.com/-/spec/opensearch/1.1/',
      'x': 'http://arxiv.org/schemas/atom'}
ARXIV = r'(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v[1-9]\d*)?'
# Six discovery families from RESEARCH_SCOPE, deliberately not inclusion rules.
QUERIES = [
 ('distributed-ai-governance', '("artificial intelligence" OR "AI") AND "governance" AND ("decentralized" OR "decentralised" OR "multi-party")'),
 ('dao-blockchain', '("AI" OR "artificial intelligence") AND "governance" AND ("DAO" OR "blockchain")'),
 ('agent-rights', '("autonomous agents" OR "AI agents") AND ("governance" OR "decision rights" OR "dispute resolution")'),
 ('verification', '"AI" AND "governance" AND ("attestation" OR "verifiable" OR "auditability") AND "decentralized"'),
 ('non-blockchain', '("AI" OR "artificial intelligence") AND "governance" AND ("multi-stakeholder" OR "federated" OR "multiparty")'),
 ('counter-evidence', '"AI" AND "decentralized" AND "governance" AND ("capture" OR "collusion" OR "limitations" OR "centralization")'),
]


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')
        tmp = Path(f.name)
    tmp.replace(path)


def doi(value):
    value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', (value or '').strip(), flags=re.I)
    return unquote(value).lower() if re.fullmatch(r'10\.\d{4,9}/\S+', value, re.I) else None


def arxiv(value):
    value = unquote(value or '')
    m = re.search(r'(?:arxiv\.org/(?:abs|pdf)/|arxiv:|10\.48550/arxiv\.)(%s)' % ARXIV, value, re.I)
    if not m:
        m = re.fullmatch(ARXIV, value)
        if not m:
            return None
        versioned = m.group(0)
    else:
        versioned = m.group(1)
    return re.sub(r'v\d+$', '', versioned), versioned


def identifiers(item):
    ids = set(item.get('identifiers', []))
    for value in [item.get('doi'), *(item.get('dois') or [])]:
        d = doi(value)
        if d:
            ids.add('doi:' + d)
            a = arxiv(d)
            if a:
                ids.add('arxiv:' + a[0])
    for value in [item.get('arxiv_id'), item.get('primary_url')]:
        a = arxiv(value)
        if a:
            ids.add('arxiv:' + a[0])
    for value in item.get('openalex_ids', []):
        ids.add('openalex:' + value.rsplit('/', 1)[-1])
    return ids


def title_key(s):
    return re.sub(r'\W+', ' ', unicodedata.normalize('NFKC', s).casefold()).strip()


def reconcile(records, item, observation):
    """Strong identity only; ambiguous bridges are held for manual reconciliation."""
    if item.get('indexing_identity_warning'):
        return {'action': 'identity_conflict', 'reason': 'Multiple arXiv IDs in one indexing record',
                'observation': observation}
    incoming = identifiers(item)
    matches = [r for r in records if identifiers(r) & incoming]
    if len(matches) > 1:
        return {'action': 'identity_conflict', 'records': [r['record_id'] for r in matches],
                'identifiers': sorted(incoming), 'observation': observation}
    record = matches[0] if matches else None
    # Even a shared DOI must not silently equate distinct arXiv works.
    if record:
        old_a = {x for x in identifiers(record) if x.startswith('arxiv:')}
        new_a = {x for x in incoming if x.startswith('arxiv:')}
        if old_a and new_a and old_a != new_a:
            return {'action': 'identity_conflict', 'records': [record['record_id']], 'observation': observation}
    action = 'matched' if record else 'new'
    if record is None:
        preferred = next((x for x in sorted(incoming) if x.startswith('arxiv:')), None)
        preferred = preferred or next((x for x in sorted(incoming) if x.startswith('doi:')), None)
        preferred = preferred or next(iter(sorted(incoming)), None)
        if not preferred:
            raise ValueError('Record without a persistent identity')
        record = {'record_id': preferred, 'first_seen_at': now(), 'versions': [], 'notes': [],
                  'screening': {'category': 'to verify', 'reason': 'Discovery metadata only; scope screening pending'}}
        candidates = []
        for other in records:
            matcher = difflib.SequenceMatcher(None, title_key(item['title']), title_key(other.get('title', '')))
            if matcher.real_quick_ratio() < .93 or matcher.quick_ratio() < .93:
                continue
            ratio = matcher.ratio()
            if ratio >= .93:
                candidates.append({'record_id': other['record_id'], 'title_similarity': round(ratio, 3),
                                   'authors_equal': item.get('authors') == other.get('authors'),
                                   'status': 'manual_verification_required'})
        if candidates:
            record['possible_duplicates'] = candidates
        records.append(record)
    record['identifiers'] = sorted(identifiers(record) | incoming)
    for field in ('title', 'authors', 'primary_url', 'publication_date', 'publication_status', 'arxiv_id', 'doi'):
        if not record.get(field) and item.get(field):
            record[field] = item[field]
    record['dois'] = sorted({x[4:] for x in record['identifiers'] if x.startswith('doi:')})
    record['openalex_ids'] = sorted({x[9:] for x in record['identifiers'] if x.startswith('openalex:')})
    record['last_seen_at'] = now()
    # Preserve source claims as observations; never overwrite screening, notes or version reading.
    observations = record.setdefault('discovery_observations', [])
    if observation not in observations:
        observations.append(observation)
    if item.get('versioned_id'):
        vid = item['versioned_id']
        if not any(v.get('arxiv_id') == vid for v in record['versions']):
            rev = re.search(r'v(\d+)$', vid)
            if rev:
                record['versions'].append({'arxiv_id': vid, 'version': int(rev.group(1)),
                    'first_seen_at': now(), 'artifacts': {}, 'reading_status': 'metadata_only_not_read'})
    return {'action': action, 'record_id': record['record_id']}


def parse_arxiv(body):
    root = ET.fromstring(body)
    total_text = root.findtext('o:totalResults', namespaces=NS)
    if total_text is None:
        raise ValueError('Invalid arXiv response: missing totalResults')
    items = []
    for e in root.findall('a:entry', NS):
        raw_id = e.findtext('a:id', '', NS)
        a = arxiv(raw_id)
        title = ' '.join(e.findtext('a:title', '', NS).split())
        if not a or not title:
            raise ValueError('arXiv error entry or missing identity/title')
        d = doi(e.findtext('x:doi', '', NS))
        items.append({'arxiv_id': a[0], 'versioned_id': a[1], 'title': title,
          'authors': [v.text for v in e.findall('a:author/a:name', NS)], 'doi': d,
          'primary_url': 'https://arxiv.org/abs/' + a[1],
          'publication_date': e.findtext('a:published', '', NS),
          'updated_date': e.findtext('a:updated', '', NS),
          'abstract': ' '.join(e.findtext('a:summary', '', NS).split()),
          'publication_status': 'arxiv deposit; review/publication status not independently verified',
          'journal_ref': e.findtext('x:journal_ref', None, NS)})
    return int(total_text), items


def parse_openalex(body):
    data = json.loads(body)
    if not isinstance(data.get('results'), list) or 'count' not in data.get('meta', {}):
        raise ValueError('Invalid OpenAlex response')
    items = []
    for w in data['results']:
        wid = w.get('id', '')
        if not re.fullmatch(r'https://openalex.org/W\d+', wid) or not w.get('title'):
            raise ValueError('OpenAlex work missing identity/title')
        locations = [w.get('primary_location') or {}, *(w.get('locations') or [])]
        urls = [u for loc in locations for u in (loc.get('landing_page_url'), loc.get('pdf_url')) if u]
        arxiv_ids = {a[0] for u in urls if (a := arxiv(u))}
        d = doi(w.get('doi'))
        ids = {'openalex:' + wid.rsplit('/', 1)[-1]}
        if d:
            ids.add('doi:' + d)
        ids.update('arxiv:' + a for a in arxiv_ids)
        # Multiple arXiv IDs in one indexing record require review, not automatic unification.
        if len(arxiv_ids) > 1:
            ids = {i for i in ids if not i.startswith('arxiv:')}
        inverted = w.get('abstract_inverted_index') or {}
        words = sorted((pos, word) for word, positions in inverted.items() for pos in positions)
        items.append({'identifiers': sorted(ids), 'openalex_ids': [wid.rsplit('/', 1)[-1]],
          'arxiv_id': next(iter(arxiv_ids)) if len(arxiv_ids) == 1 else None,
          'title': w['title'], 'authors': [a['author']['display_name'] for a in w.get('authorships', [])],
          'doi': d, 'primary_url': ('https://doi.org/' + d) if d else (urls[0] if urls else wid),
          'publication_date': w.get('publication_date'), 'updated_date': w.get('updated_date'),
          'index_created_date': w.get('created_date'), 'abstract': ' '.join(word for _, word in words),
          'publication_status': 'OpenAlex type=' + str(w.get('type')) + '; not independently verified',
          'indexing_identity_warning': sorted(arxiv_ids) if len(arxiv_ids) > 1 else None})
    return data['meta']['count'], items


def fetch(url, destination):
    # Use system curl CA store; never disable TLS checks. No auth/accounts/paid services.
    result = subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
        '--proto', '=https', '--proto-redir', '=https', '--max-time', '30',
        '--max-filesize', '10485760', '--user-agent', 'ResearcherDiscovery/0.1', url],
        capture_output=True, timeout=35)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-1000:])
    destination.write_bytes(result.stdout)
    return result.stdout


def query_url(source, query, start, end, page, size):
    if source == 'arxiv':
        terms = re.sub(r'"([^\"]+)"', r'all:"\1"', query)
        exact = f'({terms}) AND lastUpdatedDate:[{start:%Y%m%d}0000 TO {end:%Y%m%d}2359]'
        params = {'search_query': exact, 'start': (page - 1) * size, 'max_results': size,
                  'sortBy': 'lastUpdatedDate', 'sortOrder': 'ascending'}
        return 'https://export.arxiv.org/api/query?' + urlencode(params), exact
    params = {'filter': f'title_and_abstract.search:{query},from_publication_date:{start},to_publication_date:{end}',
              'sort': 'publication_date:asc', 'page': page, 'per_page': size}
    return 'https://api.openalex.org/works?' + urlencode(params), query


def window(state, source, end, start=None):
    boundary = state.get(source, {}).get('successful_through')
    return start or (date.fromisoformat(boundary) - timedelta(days=6) if boundary else end - timedelta(days=29))


def collect(project=PROJECT, sources=('arxiv', 'openalex'), start=None, end=None, page_size=25, max_pages=2):
    if page_size < 1 or page_size > 100 or max_pages < 1:
        raise ValueError('page_size must be 1..100; max_pages >=1')
    end = end or datetime.now(timezone.utc).date() - timedelta(days=1)
    if end >= datetime.now(timezone.utc).date():
        raise ValueError('Use completed UTC days only (end <= yesterday)')
    if start and start > end:
        raise ValueError('start is after end')
    for rel in ('runs', 'corpus'):
        (project / rel).mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    folder = project / 'runs' / ('collection-' + run_id)
    folder.mkdir()
    fingerprint = hashlib.sha256(json.dumps({'families': QUERIES, 'openalex_search': 'title_and_abstract.search', 'arxiv_date': 'lastUpdatedDate'}).encode()).hexdigest()
    log = {'run_id': run_id, 'type': 'manual-discovery', 'started_at': now(), 'sources': {},
           'query_fingerprint': fingerprint, 'page_size': page_size, 'max_pages_per_query': max_pages,
           'scheduled': False, 'external_delivery': False, 'events': []}
    atomic_json(folder / 'run.json', log)
    state_path = project / 'runs/collection-state.json'
    with (project / 'runs/collection.lock').open('a') as collector_lock:
        fcntl.flock(collector_lock, fcntl.LOCK_EX)
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        pending = []
        for source in sources:
            prior = state.get(source, {})
            # Changed search coverage starts a fresh 30-day window rather than skipping work.
            usable = state if prior.get('query_fingerprint') == fingerprint else {}
            since = window(usable, source, end, start)
            if since > end:
                raise ValueError('Collection end precedes source overlap window')
            source_log = {'start': str(since), 'end': str(end), 'status': 'running',
                'date_semantics': 'lastUpdatedDate' if source == 'arxiv' else 'publication_date',
                'queries': [], 'watermark_advanced': False}
            log['sources'][source] = source_log
            for family, query in QUERIES:
                qlog = {'family': family, 'query': query, 'pages': [], 'status': 'running', 'observed': 0}
                source_log['queries'].append(qlog)
                seen_pages = set()
                seen_identities = set()
                try:
                    for page in range(1, max_pages + 1):
                        if source == 'openalex' and page * page_size > 10000:
                            qlog['status'] = 'pagination_limit'
                            break
                        url, exact = query_url(source, query, since, end, page, page_size)
                        dest = folder / f'{source}-{family}-{page}.{"xml" if source == "arxiv" else "json"}'
                        request = {'url': url, 'query': exact, 'page': page, 'requested_at': now()}
                        qlog['pages'].append(request)
                        atomic_json(folder / 'run.json', log)
                        # arXiv policy: one connection, minimum 3s between calls.
                        if source == 'arxiv':
                            time.sleep(3)
                        body = fetch(url, dest)
                        total, items = (parse_arxiv if source == 'arxiv' else parse_openalex)(body)
                        digest = hashlib.sha256(body).hexdigest()
                        if digest in seen_pages:
                            raise ValueError('Repeated page; pagination not trusted')
                        seen_pages.add(digest)
                        page_identities = [tuple(sorted(identifiers(item))) for item in items]
                        if len(set(page_identities)) != len(page_identities) or seen_identities.intersection(page_identities):
                            raise ValueError('Repeated work across pages; live pagination incomplete')
                        seen_identities.update(page_identities)
                        request.update(snapshot=str(dest.relative_to(project)), sha256=digest,
                                       total_reported=total, returned=len(items), retrieved_at=now())
                        qlog['observed'] += len(items)
                        for idx, item in enumerate(items):
                            observation = {'source': source, 'run_id': run_id, 'family': family,
                                'snapshot': request['snapshot'], 'item_index': idx,
                                'retrieved_at': request['retrieved_at'], 'metadata': item}
                            pending.append((item, observation))
                        atomic_json(folder / 'run.json', log)
                        if page * page_size >= total:
                            qlog['status'] = 'complete'
                            break
                        if len(items) < page_size:
                            raise ValueError('Short/empty page before reported total; incomplete coverage')
                    else:
                        qlog['status'] = 'capped'
                except Exception as error:
                    qlog.update(status='failed', error=str(error))
                atomic_json(folder / 'run.json', log)
            source_log['status'] = 'complete' if all(q['status'] == 'complete' for q in source_log['queries']) else 'partial'
        # Reader and collector serialize their registry writes with the SAME lock.
        with (project / 'runs/registry.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            registry = project / 'corpus/references.jsonl'
            records = [json.loads(line) for line in registry.read_text().splitlines() if line.strip()] if registry.exists() else []
            for item, observation in pending:
                event = reconcile(records, item, observation)
                event.update(source=observation['source'], family=observation['family'])
                log['events'].append(event)
            with tempfile.NamedTemporaryFile('w', dir=registry.parent, delete=False) as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
                temporary = Path(f.name)
            temporary.replace(registry)
        for source, source_log in log['sources'].items():
            if source_log['status'] == 'complete':
                # An explicit retrospective run must not move a later boundary backwards.
                previous = state.get(source, {}).get('successful_through', '')
                state[source] = {'successful_through': max(previous, str(end)),
                                 'query_fingerprint': fingerprint, 'run_id': run_id}
                source_log['watermark_advanced'] = previous < str(end)
        log.update(finished_at=now(), status='complete' if all(s['status'] == 'complete' for s in log['sources'].values()) else 'partial')
        atomic_json(folder / 'run.json', log)
        # Log + registry durably written before success boundaries.
        atomic_json(state_path, state)
    counts = {action: sum(e['action'] == action for e in log['events']) for action in ('new', 'matched', 'identity_conflict')}
    return {'run': str((folder / 'run.json').relative_to(project)), 'status': log['status'],
            'sources': {s: {'status': v['status'], 'observations': sum(q['observed'] for q in v['queries']),
                           'watermark_advanced': v['watermark_advanced']} for s, v in log['sources'].items()}, **counts}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=['arxiv', 'openalex', 'both'], default='both')
    parser.add_argument('--start', type=date.fromisoformat)
    parser.add_argument('--end', type=date.fromisoformat)
    parser.add_argument('--page-size', type=int, default=25)
    parser.add_argument('--max-pages', type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(collect(sources=('arxiv', 'openalex') if args.source == 'both' else (args.source,),
        start=args.start, end=args.end, page_size=args.page_size, max_pages=args.max_pages), indent=2))
