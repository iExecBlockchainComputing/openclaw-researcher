# Local integration review — 2026-11-12

Upstream: https://github.com/Prismer-AI/Prismer/tree/2dbe71feebeb53e2a54c708cac676835e08c2f24/skills/arxiv-reader

Reviewed `SKILL.md`, `manifest.json`, and all of `index.ts`. The implementation
uses Node built-ins, retrieves arXiv metadata/source, decompresses gzip/tar into
memory, flattens ordinary LaTeX includes, and caches local text. It does not
compile TeX or execute paper-provided code. The container path can contact an
HTTP service; the local adapter deliberately disables that path.

## Local modifications

- Added a CLI that imports the TypeScript export using Node type stripping.
- Fixed a demonstrated failure on arXiv's relative `/src/...` redirect.
- Destroy timed-out download requests; cap the CLI lifetime at 50 seconds.
- Require explicit versions for full source/section reads; validate IDs before
  they are used in requests or cache paths.
- Preserve source bytes for provenance; reject obvious PDF/HTML responses on the
  LaTeX path and reject content without a recognizable LaTeX document marker.
- Keep appendices and figures in the source by default; report unresolved includes.
- Replaced upstream tool-only instructions with the invocation available locally.

These changes are in this workspace only, not submitted upstream. The original
reviewed files remain in `research-repos/Prismer` at the commit above.

## Limits

No automatic native-tool registration; no general TeX interpreter; no guarantee
of support for all tar extensions or sources; no visual figure interpretation;
no model/API calls, scheduler, DOI matching, or Slack delivery. Network and
archive handling have not received a comprehensive security audit. Do not expose
this prototype as a public service.

## Licensing

The upstream `LICENSE.md` describes MIT for named `@prismer/*` packages and BSL
1.1 for the full platform. It does not explicitly classify `skills/arxiv-reader`.
The upstream text is preserved in `UPSTREAM_LICENSE.md`. This integration is a
local non-production evaluation; do not represent this skill as unambiguously
MIT-licensed or production-cleared. Clarify applicable terms before production
rollout or redistribution. No vendor has been contacted.
