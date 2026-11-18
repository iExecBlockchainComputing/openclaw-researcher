# Weekly agent orchestration

Status: schedule authorized; job identity recorded in weekly-config.json. Read RESEARCH_SCOPE.md and WORKFLOW.md first.
Configuration: weekly-config.json. The scheduler must run an agentTurn as Researcher,
not merely execute the collector: screening and critical reading require the agent.
No further delegation. All commands below run from this project directory.

## Boundaries

Max 10 new critical readings and 5 reported papers per run, configurable. These are
ceilings, not quality thresholds or quotas. Do not claim an extracted paper is read.
Use prior verified notes for unchanged versions. Assess every candidate's abstract;
when unable to finish, mark remainder deferred and report actual coverage, never
pretend to have selected the best of an unexamined batch. Missing text is to_verify.
Keep unresolved candidates available for follow-up; no automatic rejection by rank.

## Run protocol

1. Create a unique runs/weekly-<UTC timestamp>/ directory and a run.json journal.
   Check prior weekly journals before proceeding. If a prior run is active or its
   delivery is uncertain, stop and report rather than overlap or resend. A crashed
   run remains incomplete; do not infer it succeeded.
2. Run `.venv/bin/python scripts/collect.py --source both --page-size 100 --max-pages 10`.
   Use config values if changed. Capture stdout, stderr, exit code and exact returned
   collection log path. Collection window/resumption is handled by collect.py.
   Never advance collection boundaries yourself. Partial source coverage is allowed
   only if explicitly disclosed in the digest; total failure yields a failure report,
   not an empty-results claim. Do not auto-increase caps or retry indefinitely.
3. Run `.venv/bin/python scripts/weekly.py prepare --collection-log <collection run.json>
   --output <weekly directory>/packet.json` (one line). This includes this collection's
   references plus the known main corpus backlog. It does not impose a candidate cap.
   Read the packet in bounded batches. Review previous deferred decisions as well;
   include additional deferred references in the packet, documenting that addition.
4. Assess metadata/abstracts against scope. Reuse unchanged prior decisions explicitly;
   a new version needs review even when the work was previously rejected or read.
   Save decision.json with assessments for every candidate, including deferred ones.
   Pick up to max_new_full_reads for deeper reading on relevance, evidence, novelty
   and critical findings, not raw citation counts. No automatic score-only rejection.
5. For arXiv, resolve the exact version and use read_paper.py. For other primary
   documents obtain the original text and record equivalent version-specific evidence;
   if unavailable, leave to_verify. Read relevant sections, figures and supplements,
   write sourced notes and update registry under registry.lock per WORKFLOW.md.
   Keep previous versions/decisions. Record actual reading coverage and failures.
6. Select at most max_digest_papers with adequate evidence, possibly zero. Compare
   against prior CONFIRMED delivery receipts. Do not repeat an unchanged version.
   A substantively changed version may appear with an explicit update rationale.
   Never infer publication from existence of a draft or reading note.
7. Save a concise French digest under digests/ with exact source date windows,
   coverage limitations, version links, contribution and principal limitation per
   paper. Separate empty relevant results from collection/reading failures.
8. Validate structurally with `scripts/weekly.py validate --packet <packet.json>
   --decision <decision.json> --output <weekly directory>/validation.json`, using
   .venv/bin/python. Review claims/citations manually too. Failed validation blocks
   publication, not preservation of partial work.
9. Delivery is DISABLED until schedule/destination are configured with the user.
   In draft mode stop here, returning artifact paths, counts and limitations.
   Once authorized: read the Slack skill; send the saved digest only to the configured
   account/channel/thread. Keep scheduler automatic delivery NONE to avoid a second
   copy. Before sending record delivery_pending and digest hash; after confirmed
   success record returned message ID, account, destination, version IDs, hash and
   timestamp in receipt.json, then mark sent. If outcome is uncertain, mark uncertain
   and stop: do not retry blindly. A later run must reconcile that receipt first.
10. Close run.json with completed/draft_only/partial/failed/uncertain status, counts
    examined/read/selected/deferred, artifact paths, source windows and errors.

## decision.json schema example

```json
{
  "assessments": [
    {"record_id": "arxiv:example", "decision": "already_read", "reason": "Unchanged verified version"}
  ],
  "selected": [
    {"record_id": "arxiv:example", "version": "examplev1", "note": "corpus/notes/examplev1.md", "reason": "Relevant mechanism with explicit evidence"}
  ],
  "draft": "digests/example.md"
}
```

Valid assessment decisions: read, already_read, rejected, deferred, to_verify.
A read decision counts against the new-reading budget, including unsuccessful attempts.
Non-arXiv version objects use version_id plus reading_status and reading_coverage.note.
The helper validates storage/budget structure, NOT scientific truth or delivery history.

## Offline rehearsal

Omit --collection-log in prepare to build an offline registry snapshot. It does not
fetch papers, alter the registry, update collection state or send messages. This is
an engineering rehearsal, NOT a successful fresh weekly literature review.

## Activation inputs still required

Day/time in Europe/Paris and exact Slack account/channel (thread if desired).
Use OpenClaw automations with an isolated Researcher agentTurn referencing this file
by absolute path, delivery mode none. Verify saved job before enabling. Do not create
an arbitrary time/destination. The currently visible automation list is caller-scoped;
absence from that list is not proof no other Gateway job exists.

## Activated scheduler delivery contract (supersedes steps 9–10 delivery mechanism)

Monday 09:00 Europe/Paris; Slack default account, channel C0CFAVAV91N.
The job uses OpenClaw announce delivery. Do NOT call message send: return the saved
validated French digest as the final answer so the scheduler delivers it once.
Store delivery_pending, version IDs and digest hash before final output. Do not mark
sent merely for producing a final answer. On the next run, inspect the previous
job run using automations action=runs and require confirmed delivered status before
recording a receipt. Failed/uncertain delivery must be reported, never silently retried.
If history cannot resolve delivery, stop and report the ambiguity.
Operational failures should produce a short failure report, not a fabricated digest.
No operational file paths or internal assessment labels in the published digest.
The scheduled job starts at 09:00; publication follows completed analysis.

## Editorial rules — 2026-11-17 (take precedence over everything above)

Clean slate: on 2026-11-17 the registry, notes, downloaded papers, digests and
collection state were archived under archive/reset-20261117/ and reset. Do not read
the archive to decide novelty. The registry starts empty; the first run collects the
initial 30-day window. A paper is excluded only if it is already in the current
registry as read, or in a digest delivered by a run recorded as delivered. There is no
separate notion of "internal" versus "channel" novelty.

Tone: the Slack message is written by a colleague, not a system. Open with a short
greeting in French (e.g. "Bonjour à tous,") and one sentence introducing the week's
selection, then the numbered paper notices, then a brief friendly closing line.
Warm but concise; no jargon about the pipeline.

Notices: up to five, numbered. Each has title + primary version link, what the paper
studies in plain French, its contribution/result, and one principal limitation.
Do not publish registry counts, observation counts, assessment statuses, pending
queues, test history or phrases about the collection process. Keep these in run logs.
Mention source coverage limitations in at most one short footer when materially
relevant. Distinguish a paper's date from the date it is shared. Never call an older
paper newly published. The 10-reading ceiling applies to new reading work.

Silent execution (scheduler announce delivers ALL assistant text of the run, not only
the last message): never write text between tool calls — no progress notes, no status
sentences, no "validation OK", no narration of what is being read. Use tools silently.
The only text you output in the whole run is the final digest, starting directly with
the greeting. Journal and delivery-pending notes go to files, not to the answer.
