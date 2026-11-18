---
name: arxiv-reader
description: Fetch abstracts, section outlines, and version-pinned LaTeX sources of arXiv papers for critical reading. Use for arXiv IDs and paper-reading requests; this skill does not schedule monitoring or publish results.
metadata:
  openclaw:
    emoji: 📄
    requires:
      bins: [node]
---

# arXiv Reader — local OpenClaw adapter

Adapted from Prismer's `skills/arxiv-reader` at commit
`2dbe71feebeb53e2a54c708cac676835e08c2f24`.
The upstream TypeScript export does not automatically register callable tools in
OpenClaw. Use the bundled CLI through the execution tool instead.

## Invoke

Resolve `scripts/run.mjs` relative to this skill directory. Node 22.6+ with
experimental type stripping (tested on 22.16.0) is required.

```sh
node --experimental-strip-types /ABSOLUTE/SKILL/DIR/scripts/run.mjs abstract 2605.24538v1
node --experimental-strip-types /ABSOLUTE/SKILL/DIR/scripts/run.mjs sections 2605.24538v1
node --experimental-strip-types /ABSOLUTE/SKILL/DIR/scripts/run.mjs fetch 2605.24538v1 --cache-dir /ABSOLUTE/PAPER/DIR/cache --output /ABSOLUTE/PAPER/DIR/source.json
```

The output directory must already exist. `fetch` returns full flattened LaTeX in
JSON, without removing appendices or figure environments. `sections` returns an
outline. `abstract` tries the arXiv Atom API, then falls back to the source.
For `fetch` and `sections`, an explicit version suffix is required to avoid
serving an indefinitely stale cache under an unversioned identifier. Resolve the
version from arXiv metadata before reading. Never infer that extracted text means
it has already been read or verified.

## Coverage and failure handling

- Keep source links, exact versions, and reading coverage in the task's records.
- Inspect unresolved includes and relevant figures, tables, and appendices;
  flattened LaTeX is not a visual rendering and bibliography files are not expanded.
- The parser supports ordinary tar/gzip and LaTeX includes, not all TeX macros or
  archive extensions. Do not execute or compile downloaded TeX.
- On source/network/format failure, report it and use a PDF or HTML reading path
  when available. Never substitute an abstract-only analysis for full reading.
- The adapter uses standalone mode, validates IDs, handles relative redirects,
  retains downloaded source bytes, and bounds run time. It does not register
  native tools, start a container service, or send messages.

## Project integration

For `decentralized-ai-governance`, read its scope and `WORKFLOW.md` from the
workspace project directory. Its `scripts/read_paper.py` links artifacts to the
reference registry and provides a PDF-text fallback in the project's isolated
Python environment. This project integration is not needed for unrelated papers.

## Provenance

See `references/LOCAL_ADAPTATION.md` for reviewed files, local changes, known
limitations, and upstream licensing information. No production-readiness claim is made.
