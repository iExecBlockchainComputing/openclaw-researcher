# Paper reading workflow

This project supports discovery, ingestion and reading. Weekly Researcher orchestration is enabled; see WEEKLY.md and weekly-config.json.
Read `RESEARCH_SCOPE.md` first. Do not publish to Slack from this workflow unless
explicitly requested. No collection watermark is advanced by reader tests.

## Storage

- `corpus/references.jsonl`: one logical record per known work (arXiv, DOI or OpenAlex identity); version
  entries retain source/PDF artifacts, hashes, extraction coverage and reading status.
- `corpus/papers/<versioned-id>/`: metadata snapshot, source archive, flattened
  LaTeX, optional PDF and page-numbered extracted text. Slash IDs use underscores.
- `corpus/notes/`: evidence-linked reading notes, named with the versioned ID.
- `digests/`: future dated monitoring summaries; reset 2026-11-17; previous material archived under archive/reset-20261117/.
- `runs/`: ingestion and collection logs, response snapshots, tests, locks and per-source manual collection state.

## Runtime

From the Researcher workspace root:

```sh
projects/decentralized-ai-governance/.venv/bin/python \
  projects/decentralized-ai-governance/scripts/read_paper.py 2605.24538v1
```

The command tries the locally adapted arxiv-reader source path first, then PDF
text extraction on source failure. To exercise the PDF path directly:

```sh
projects/decentralized-ai-governance/.venv/bin/python \
  projects/decentralized-ai-governance/scripts/read_paper.py 2605.24538v1 --mode pdf
```

Resolve the version on the original arXiv page first; an unversioned input is
rejected. The reader uses Node 22.6+ type stripping and Python with pypdf from
the local `.venv` (see `requirements-reader.txt`). No model/API key is required.
Recreate the virtual environment if needed with `python3 -m venv .venv` from this
project directory, then `.venv/bin/python -m pip install -r requirements-reader.txt`.

Already-ingested artifacts of the requested type return `already_known` without
another download. The reader reuses records identified by the collector through their arXiv identity,
even if the canonical record ID originated in DOI/OpenAlex. Cross-source discovery
and matching are documented below. No continuous/scheduled collection is enabled.

## Read and record

1. Check metadata, title, authors and exact version against the original page.
2. Screen using the scope: `main`, `context`, `to verify`, or `rejected`, with a
   reason. Label an older integration-test paper as such, not a current discovery.
3. Inspect sections, source, and relevant figures/tables/appendices. The PDF
   fallback extracts every page but performs no OCR. Low-text pages are flagged;
   a successful extraction does not prove semantic or visual completeness.
4. Write a note using `corpus/notes/TEMPLATE.md`. Cite version-pinned URLs and
   section/page evidence; distinguish claims, observations, interpretation, unknowns.
5. Update the registry under the same `runs/registry.lock` advisory lock. Preserve
   all existing fields and versions, write atomically, and link the note using
   project-relative paths. Mark the version's actual `reading_status` and
   `reading_coverage` separately from extraction metadata. Do not automatically
   mark other versions as read.
6. Record checks and limitations in the run log. A failed read must not advance
   any future collector's successful-source boundary.

The source parser is lightweight; complex TeX, archive extensions, and figures
may need an alternate path. No downloaded TeX is executed. Filenames and IDs are
validated, but this prototype is not a fully audited ingestion service.

## Integration test

`corpus/notes/2605.24538v1.md` is the first test note. The paper is from May 2026
and was deliberately selected for subject relevance, not publication recency.
The technical acceptance report is in `runs/reader-integration-2026-11-12.md`.


## Manual collection — implemented 2026-11-17

```sh
projects/decentralized-ai-governance/.venv/bin/python \
  projects/decentralized-ai-governance/scripts/collect.py
```

Standard-library Python plus system `curl` (TLS validation on); no account, API key,
paid service, schedule or Slack send. Python's CA store was unavailable on the test
host, so the collector uses the validated system curl trust store, like the reader.
Do not create an OpenAlex account or request a key automatically on access failure.

Defaults: both sources, six query families from `RESEARCH_SCOPE.md`, 25 results per
page, at most 2 pages per family/source (at most 600 observations). Queries are in
`scripts/collect.py`; exact requests, date filters, counts, pages, errors, SHA-256
hashes and raw responses are saved under `runs/collection-<UTC timestamp>/`.
Observations link to snapshots and item positions in the shared reference registry.
A source's raw metadata are evidence of discovery, not a verified research finding.

The first window covers 30 completed UTC days ending yesterday. An incremental
run starts six days before the last successful inclusive end (seven inclusive days
of overlap). `--start YYYY-MM-DD --end YYYY-MM-DD` selects an explicit historical
window; `--source arxiv|openalex|both`, `--page-size 1..100`, `--max-pages N` bound
work. Today's unfinished UTC day cannot be marked complete. A query change resets
the default search window; the query fingerprint is recorded with boundaries.

arXiv uses `lastUpdatedDate` (including revisions of older works), OpenAlex uses
`publication_date`. These are NOT equivalent coverage: the free OpenAlex run is
not an indexing/update feed and can miss delayed indexing and older revisions.
Overlap does not eliminate this limitation. OpenAlex is explicitly restricted to `title_and_abstract.search`; the initial
full-text probe was noisy and is retained as a separately logged partial run. Six families are not an exhaustive
review. Pagination is over live indexes, not a frozen snapshot.

Each source advances `runs/collection-state.json` only if ALL of its queries reach
their reported result count. Caps, short/repeated pages and errors leave that
source's boundary unchanged. The other source can succeed independently. Raw
responses from partial runs are retained and valid observations still ingested.
A `running` journal after interruption is not successful coverage. Successful
registry/log writes precede state advancement; interrupted requests may be retried.
Anonymous OpenAlex uses basic paging (up to 10,000 results), not authenticated
cursor paging. arXiv requests are sequential and spaced by at least 3 seconds.

Matching policy:

- Normalize DOI forms/case, base arXiv IDs and OpenAlex work IDs. Retain versions
  separately. Resolve arXiv identities from OpenAlex locations and arXiv DOIs.
- Match on an explicit shared identifier; keep all source observations, dates,
  DOI aliases and versions. Never overwrite screening, notes, artifacts or prior
  version reading status. New discoveries are `to verify`, not auto-included.
- Similar titles (threshold 0.93) are only `possible_duplicates` candidates, even
  with identical author lists. A human/agent must verify the relationship.
- Multiple existing records linked by a new bridge, or conflicting arXiv IDs,
  produce `identity_conflict` events containing the original observation. They
  are not destructively merged. Review these before treating counts as final.
- Preprint/publisher relationships lacking a common identifier are unresolved;
  do not claim exhaustive preprint-to-publication matching.

Screen the batch manually against the main inclusion criterion. Log category,
reason and actual evidence coverage. Metadata/abstract screening is not full-text
reading; absent abstracts remain `to verify` unless other evidence suffices.
The collector never changes an existing screening decision. Subsequent manual
screening must use `runs/registry.lock` and an atomic registry replacement.

Tests (offline fixtures outside the real corpus):

```sh
projects/decentralized-ai-governance/.venv/bin/python -m unittest discover \
  -s projects/decentralized-ai-governance/scripts -p 'test_*.py' -v
```

API references checked 2026-11-17:
[arXiv API](https://info.arxiv.org/help/api/user-manual.html),
[OpenAlex filters](https://help.openalex.org/api/filtering/),
[paging](https://help.openalex.org/api/paging/),
[authentication](https://help.openalex.org/api/authentication/).

## Five-paper reading test — 2026-11-17

The manual chain through a saved, unsent Slack draft was exercised on five selected
papers. See [report](runs/five-paper-e2e-2026-11-17.md) for notes, actual reading
coverage, checks and limitations. This test does not establish weekly quotas,
enable a schedule, or authorize publication.

## Weekly orchestration — prepared, not activated

See [WEEKLY.md](WEEKLY.md) and [weekly-config.json](weekly-config.json).
`scripts/weekly.py` prepares agent work packets and validates draft structure.
The agent still performs screening and critical reading. Offline rehearsal:
[runs/weekly-offline-rehearsal-2026-11-17/validation.json](runs/weekly-offline-rehearsal-2026-11-17/validation.json).
Schedule activated: Monday 09:00 Europe/Paris, Slack C0CFAVAV91N. Job ID is in weekly-config.json; scheduler delivery is announce.
