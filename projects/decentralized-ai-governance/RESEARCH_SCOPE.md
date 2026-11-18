# Research Monitoring Scope — Decentralized AI Governance

**Project:** `decentralized-ai-governance`  
**Version:** 0.2 — adapted for continuous monitoring  
**Updated:** 2026-11-10  
**Purpose:** the project's scientific reference for Researcher, not the agent's exclusive specialization.

## 1. Objective and guiding questions

Continuously identify and analyze research on the governance of AI systems
(models, agents, and execution infrastructure) without a single central authority.
Assess how mechanisms distribute decision-making power and organize
accountability, contestability, and verification of rule enforcement.
These properties are questions to investigate, never assumed guarantees.

Guiding questions:

1. Which mechanisms distribute rights to make decisions, exercise control, or
   modify rules among multiple parties?
2. Who can verify what, using which evidence and trust assumptions?
3. How are autonomous agents, their permissions, interactions, resources, and
   any assets they hold governed?
4. What empirical findings, limitations, centralized dependencies, attacks, or
   failures are documented? What recourse mechanisms exist?
5. What has changed relative to previously identified work, and why does it
   warrant an in-depth reading?

This is neither an exhaustive corpus nor, at this stage, a systematic review.

## 2. Operational definitions

**Governance:** defining and modifying rules; allocating decision rights and
permissions; controlling resources; oversight; accountability; contestation,
recourse, and sanctions.

**Decentralization or multi-party governance:** explicitly distributing authority,
control, or decisions among multiple actors. Describe which powers are actually
distributed and which remain concentrated. A distributed system, a blockchain,
or multiple agents alone do not establish this property.

**Verifiability:** the ability to check a precisely defined property.
Distinguish proofs of computation, execution attestations, auditability, compliance
with a rule, decision quality, and the legitimacy of that rule. Do not conflate
them. Confidentiality and verifiability are separate dimensions.

## 3. Scientific scope

### Included in the main corpus

- Decentralized or multi-party mechanisms for governing AI systems.
- DAOs, blockchains, smart contracts, and protocols applied to such governance.
- Governance of autonomous agents and multi-agent systems: permissions,
  collective rules, incentives, resources, accountability, and dispute resolution.
- Cryptographic proofs, ZKPs, TEEs, attestations, and audit logs when they support
  an identifiable decentralized or multi-party governance mechanism.
- Federated learning when it addresses decision rights, participation, control,
  accountability, or governance among participants.
- Critical, theoretical, or empirical studies of these mechanisms, including
  negative findings or a lack of claimed guarantees.
- Interdisciplinary work connecting the technical and institutional dimensions
  of such governance; proposing a protocol is not a requirement.

### Excluded from the main corpus

- Regulatory or institutional analyses without an explicit connection to a
  decentralized or multi-party AI governance mechanism.
- AI used to improve a blockchain, without governance of AI itself.
- Distributed inference, federated learning, agent coordination, or verifiable
  computation addressing performance alone, without an explicit governance link.
- Generic corporate governance unrelated to AI.

### Supplementary context

Work on centralized governance, a technical primitive, or an institutional text
may be retained as **context** when its comparative usefulness is explained.
It must not be counted as a finding in the main corpus.

## 4. Sources and types of evidence

**Initially planned collection sources:** arXiv and OpenAlex. These are discovery
channels; consult the original document before attributing a finding to it.
Report the actual coverage of each run.

**Further investigation:** official publication and conference pages, OpenReview,
reference lists, and citing works when accessible; original documentation, code,
specifications, and audits to verify an implementation.
Adding connectors or paid services is not implicitly authorized.

Distinguish peer-reviewed publications, preprints, technical reports,
specifications, audits, and announcements. For a preprint, state that the
consulted version has not been peer reviewed when that status is established;
do not assume that an arXiv deposit rules out a published version.
A commercial announcement is a lead to verify, not evidence of a result.

## 5. Discovery queries

Search primarily in English, without excluding relevant documents in another
accessible language. Combine the families below; do not require every concept
to appear simultaneously.

| Family | Indicative terms |
|---|---|
| AI | artificial intelligence, AI systems, AI agents, autonomous agents, multi-agent systems |
| Governance | governance, decision rights, collective decision-making, oversight, accountability, dispute resolution, access control |
| Distribution of power | decentralized, decentralised, distributed governance, multi-party, multiparty, multi-stakeholder, DAO, federation, protocol governance |
| Verification and trust | verifiable, zero-knowledge, attestation, trusted execution environment, auditability, trust assumptions |
| Critical and counter-evidence analysis | limitations, failure, attack, collusion, capture, centralization, centralisation, empirical evaluation |

Query families to adapt to each source's syntax:

1. AI governance + decentralization / multiple parties.
2. DAO / blockchain + AI governance.
3. Autonomous agents + decision rights / oversight / disputes + collective governance.
4. Decentralized AI governance + verification / attestation / audit.
5. Multi-party AI governance outside blockchain.
6. Selected mechanisms + criticism / capture / collusion / empirical evaluation.

Record the exact queries and filters actually executed. Keywords are discovery
aids, not sufficient selection criteria.

## 6. Time windows and incremental tracking

- **No fixed end date:** monitoring evolves with each collection run.
- **Proposed initial window:** the previous 30 days for the first collection;
  this operational setting remains adjustable. It is not a historical search.
- **Subsequent collections:** resume from each source's last successful collection
  boundary, with a default overlap of 7 days.
- Do not advance a source's boundary after a failure, incomplete pagination, or
  interrupted collection; record partial coverage and resume missing portions.
- Distinguish first publication date, update/version date, indexing date when
  available, and the date the monitoring process discovered the work.
- Overlap reduces omissions without guaranteeing detection of all indexing
  delays; use broader catch-up windows if gaps emerge.
- Older work remains eligible as context, prior work, or a late discovery,
  explicitly labeled as such. The period from 2020 onward is a reference point
  for retrospective searches, not an absolute exclusion of foundational work.

## 7. Selection, deduplication, and priority

### Main inclusion criterion

A work must address AI governance **and** a distribution of authority, control,
or decision-making among multiple parties. It may analyze or criticize that
distribution without proposing it. Verifiability alone is not sufficient.

### Handling incomplete cases

- Missing abstract or inaccessible text: mark **to verify**, without inventing
  content or automatically rejecting a potentially relevant publication.
- Abstract only: provisional screening is possible, never presented as a full reading.
- Non-academic text: retain separately if it directly documents a mechanism,
  implementation, or failure; explain its status and limitations.
- Rejection: retain a brief reason to avoid repeating the same screening.

### Identities and versions

Group records by DOI, arXiv identifier, and version relationships; otherwise,
compare titles and authors and verify the match. Link the preprint, revisions,
and final publication under one logical reference. Preserve the history.
A substantive update may warrant a new alert rather than being treated as a mere duplicate.

### Reading priority

Prioritize relevance to the guiding questions, novelty relative to the corpus,
quality of evidence, explicit assumptions, reproducibility, and contradictory
findings. Citations, votes, and visibility are neither scientific validation
nor grounds for excluding little-known work.

## 8. Reading notes and reporting

For each retained reference, record:

- Title, authors, primary URL, DOI/ID, version, dates, and known publication status.
- Inclusion rationale; category **main / context / to verify / rejected**.
- Object being governed, actors, decision rights, and concrete mechanism.
- Trust assumptions, residual centralized powers, and threat model.
- Properties actually verified and properties not demonstrated.
- Method, evaluations, comparisons, findings, and reproduction resources.
- Accountability, recourse, limitations, failure risks, and documented criticisms.
- Contribution relative to previously identified references and relevance to the project.
- References to sections, pages, figures, or tables for important conclusions.
- Reading coverage: metadata, abstract, specified sections, or full text;
  state separately whether relevant figures and appendices were consulted.

Distinguish authors' claims, verified observations, Researcher's interpretations,
and unknowns. Do not infer a guarantee from the name of a technology.

A monitoring digest states the period covered, sources consulted, new findings,
updated versions, and collection limitations. If no relevant results are found,
report this without silently broadening the scope.

## 9. Traceability and operation

### Project storage layout

All paths below are relative to the Researcher workspace root:

```text
projects/decentralized-ai-governance/
├── RESEARCH_SCOPE.md
├── corpus/
│   ├── references.jsonl   # Metadata, source links, identifiers, versions, and status
│   ├── papers/           # Downloaded PDFs or paper sources
│   └── notes/            # Sourced reading notes
├── digests/              # Dated monitoring digests
└── runs/                 # Collection logs and per-source resumption boundaries
```

The storage layout was initialized on 2026-11-12 for a single-paper reader test.
This does not imply that scheduled monitoring or continuous collection has started.
Manual arXiv/OpenAlex discovery and cross-source identity matching were added on
2026-11-17. Read `WORKFLOW.md` for implemented collection, ingestion and reading
procedures, including per-source date semantics and partial-coverage handling.

`corpus/references.jsonl` is the local reference registry used for deduplication
and tracking versions and screening decisions. Downloaded documents and reading
notes must be linked from their registry records. If a document is unavailable,
retain its source link and access status without claiming it was downloaded or read.
Slack is a delivery channel, not the primary archive.

### Collection records and activation

Future collections will retain references and versions, reading notes, screening
decisions, and run logs in the project directory. Each log will record sources,
queries, filters, time boundaries, caps/pagination, observed counts, and errors.
Resumption boundaries will remain separate for each source.

Frequency, collection budget, number of references to report, and destinations
will be defined in the routine configuration. **This file does not activate any
scheduled run or Slack publication.** Sending permissions will be limited to
the scope explicitly requested by the user.

## 10. Known limitations

- Two planned collection sources, with partial coverage and variable indexing.
- Primarily English-language queries; recent and unstable terminology.
- Dates and filters are not equivalent across sources; each run must document them.
- Result caps, text access, and extraction quality may limit coverage.
- Preprints and technical documents may evolve; check versions.
- Monitoring does not replace a systematic review or experimental validation.
