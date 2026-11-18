#!/usr/bin/env python3
"""Version-pinned arXiv ingestion; no scheduler, LLM calls, or Slack delivery."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT.parents[1]
RUNNER = WORKSPACE / 'skills/arxiv-reader/scripts/run.mjs'
ID_PATTERN = r'(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})v[1-9]\d*'


def now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def download(url, destination):
    # No shell interpolation, no disabled TLS verification, bounded retries/time.
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as f:
        temporary = Path(f.name)
    try:
        subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
                        '--max-time', '40', '--max-filesize', '52428800',
                        '--proto', '=https', '--proto-redir', '=https',
                        '--output', str(temporary), url], check=True, timeout=45,
                       capture_output=True)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name', '').startswith('citation_'):
            self.values.setdefault(attrs['name'], []).append(attrs.get('content', ''))


def extract_pdf(pdf, output):
    from pypdf import PdfReader
    reader = PdfReader(pdf)
    pages = [page.extract_text() or '' for page in reader.pages]
    output.write_text('\n\n'.join(f'--- Page {i + 1} ---\n{text}' for i, text in enumerate(pages)))
    return {'total_pages': len(pages), 'pages_attempted': len(pages),
            'low_text_pages': [i + 1 for i, text in enumerate(pages) if len(text.strip()) < 80],
            'ocr_used': False, 'figures_visually_reviewed': False}


def ingest(arxiv_id, mode='auto'):
    if not re.fullmatch(ID_PATTERN, arxiv_id):
        raise ValueError('Use an explicit versioned arXiv ID, e.g. 2605.24538v1')
    base_id, revision = arxiv_id.rsplit('v', 1)
    slug = arxiv_id.replace('/', '_')
    folder = PROJECT / 'corpus/papers' / slug
    folder.mkdir(parents=True, exist_ok=True)
    for rel in ('corpus/notes', 'runs', 'digests'):
        (PROJECT / rel).mkdir(parents=True, exist_ok=True)
    registry_path = PROJECT / 'corpus/references.jsonl'
    registry_path.touch(exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    log = {'run_id': run_id, 'type': 'single-paper-reader-test', 'started_at': now(),
           'arxiv_id': arxiv_id, 'mode': mode, 'status': 'running', 'errors': [],
           'collection_window': None, 'source_watermarks_advanced': False}
    try:
        # Lock the whole read/update operation; no concurrent lost registry updates.
        with (PROJECT / 'runs/registry.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            records = [json.loads(line) for line in registry_path.read_text().splitlines() if line.strip()]
            record = next((r for r in records if r['record_id'] == 'arxiv:' + base_id or r.get('arxiv_id') == base_id or 'arxiv:' + base_id in r.get('identifiers', [])), None)
            version = next((v for v in record['versions'] if v['arxiv_id'] == arxiv_id), None) if record else None
            requested_text = folder / ('pdf.txt' if mode == 'pdf' else 'source.tex')
            if mode == 'auto' and not requested_text.exists():
                requested_text = folder / 'pdf.txt'
            if version and requested_text.exists() and requested_text.stat().st_size:
                log.update(status='already_known', finished_at=now(), files=[str(requested_text.relative_to(PROJECT))])
                save_json(PROJECT / 'runs' / (run_id + '.json'), log)
                return {'status': 'already_known', 'record_id': record['record_id'], 'arxiv_id': arxiv_id}

            metadata_file = folder / 'metadata.html'
            if not metadata_file.exists():
                download('https://arxiv.org/abs/' + arxiv_id, metadata_file)
            metadata = Metadata()
            metadata.feed(metadata_file.read_text())
            title = metadata.values.get('citation_title', [''])[0]
            if not title:
                raise ValueError('arXiv metadata missing citation_title; refusing an unidentified record')
            metadata_id = metadata.values.get('citation_arxiv_id', [''])[0]
            if metadata_id and metadata_id not in (arxiv_id, base_id):
                raise ValueError('Metadata identifier does not match requested paper')

            read_method = None
            coverage = {}
            if mode == 'auto':
                try:
                    result = subprocess.run(['node', '--experimental-strip-types', str(RUNNER),
                        'fetch', arxiv_id, '--cache-dir', str(folder / 'cache'),
                        '--output', str(folder / 'source.json')], capture_output=True, text=True,
                        timeout=55, check=True)
                    source = json.loads((folder / 'source.json').read_text())['content']
                    (folder / 'source.tex').write_text(source)
                    unresolved = re.findall(r'Could not resolve: ([^\n]+)', source)
                    read_method = 'latex-source'
                    coverage = {'appendices_removed': False, 'figures_removed': False,
                                'unresolved_includes': unresolved, 'figures_visually_reviewed': False,
                                'characters': len(source)}
                except (subprocess.SubprocessError, ValueError, KeyError) as error:
                    detail = getattr(error, 'stderr', None) or str(error)
                    log['errors'].append({'stage': 'source', 'detail': str(detail)[-2000:]})
            if read_method is None:
                pdf = folder / 'paper.pdf'
                if not pdf.exists():
                    download('https://arxiv.org/pdf/' + arxiv_id, pdf)
                if not pdf.read_bytes().startswith(b'%PDF-'):
                    raise ValueError('Expected a PDF, not an HTML error page')
                coverage = extract_pdf(pdf, folder / 'pdf.txt')
                read_method = 'pdf-text'

            paths = sorted(str(p.relative_to(PROJECT)) for p in folder.rglob('*') if p.is_file())
            hashes = {str(p.relative_to(PROJECT)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in folder.rglob('*') if p.is_file()}
            if record is None:
                record = {'record_id': 'arxiv:' + base_id, 'arxiv_id': base_id, 'title': title,
                          'authors': metadata.values.get('citation_author', []),
                          'doi': metadata.values.get('citation_doi', [None])[0],
                          'primary_url': 'https://arxiv.org/abs/' + base_id,
                          'publication_date': metadata.values.get('citation_date', [None])[0],
                          'first_seen_at': now(), 'publication_status': 'arxiv-preprint; peer-review status not independently verified',
                          'screening': {'category': 'to verify', 'reason': 'Awaiting human/agent scope screening'},
                          'notes': [], 'versions': []}
                records.append(record)
            if version is None:
                version = {'arxiv_id': arxiv_id, 'version': int(revision), 'first_seen_at': now(),
                           'artifacts': {}, 'reading_status': 'downloaded_not_yet_read'}
                record['versions'].append(version)
            version['artifacts'][read_method] = {'paths': paths, 'sha256': hashes,
                                                'coverage': coverage, 'retrieved_at': now()}
            record['last_seen_at'] = now()
            # Atomic write after all artifacts have been validated.
            with tempfile.NamedTemporaryFile(mode='w', dir=registry_path.parent, delete=False) as f:
                for item in records:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
                temporary = Path(f.name)
            temporary.replace(registry_path)
            log.update(status='success', finished_at=now(), method=read_method, coverage=coverage, files=paths)
            save_json(PROJECT / 'runs' / (run_id + '.json'), log)
            return {'status': 'success', 'arxiv_id': arxiv_id, 'title': title,
                    'method': read_method, 'coverage': coverage, 'record_id': record['record_id']}
    except Exception as error:
        log.update(status='failed', finished_at=now())
        log['errors'].append({'stage': 'ingestion', 'detail': str(error)})
        save_json(PROJECT / 'runs' / (run_id + '.json'), log)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arxiv_id')
    parser.add_argument('--mode', choices=['auto', 'pdf'], default='auto')
    args = parser.parse_args()
    print(json.dumps(ingest(args.arxiv_id, args.mode), ensure_ascii=False, indent=2))
