---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S120'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W05.P17.S120 semantic raw-ID leakage audit

Scope:
- `vaultspec-rag`

## Description

- Verify `vaultspec-rag` service readiness.
- Run semantic searches for operator-facing raw `work_unit_id` and `calculation_revision_id` copy/paste workflows in docs, locales, CLI handlers, and adjacent commands.
- Run semantic searches for internal service pointer linkage across current and filed calculation revision surfaces.

## Outcome

Semantic discovery over the current tree did not find a common operator workflow that
still requires carrying a raw `work_unit_id` or `calculation_revision_id` between
commands.

Search evidence:

- `operator must copy paste work unit id calculation revision id modelo CLI workflow`
  returned internal service calls, tests, exact-ID implementation surfaces, and the
  tutorial completion text that explicitly says the workflow no longer requires
  copying raw internal IDs between commands.
- `modelo work calculate verify file export natural key current revision selector
  filed verified draft` returned selector functions, selector tests, and current
  documentation for natural-key defaults.
- `locale help message pass work unit id calculation revision id modelo command`
  returned exact-ID command arguments and low-level application function signatures,
  not stale locale guidance forcing copied IDs for the standard path.

Classification:

- Keep: internal application APIs and domain objects that accept or store exact IDs
  for audit, replay, persistence, and machine consumers.
- Keep: CLI exact-ID arguments on adjacent/advanced commands where they are retained
  as explicit escape hatches.
- Keep: structured JSON payload fields that expose internal IDs for automation.
- Keep: tests that seed or assert internal ID behavior.
- Pass: narrative docs now route tutorial, quickstart, Modelo 303/390, reconcile,
  and filing-spine workflows through `--modelo`, `--year`, and `--period`.
- Pass: selector semantics found by RAG align with command-specific defaults for
  current draft, current verified, and filed/exportable revisions.

## Notes

- `vaultspec-rag server service status` reported a ready service on port 8766 before
  the audit.
- Broad RAG searches completed successfully through the running service.
- Semantic closure is limited to operator-facing leakage; exact IDs deliberately
  remain present in the internal and advanced-addressing surfaces described above.
