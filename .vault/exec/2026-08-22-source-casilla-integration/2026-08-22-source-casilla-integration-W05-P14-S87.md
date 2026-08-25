---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:969a0a548a874a90c970ff1645a4ea0c8a1f6cfe14747650a5f6ab461044452e'
step_id: 'S87'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# define the application command that accepts assembled typed row observations for calculation

## Scope

- `src/cadrumo/application/calculations/_row_set_assembly.py`
- `src/cadrumo/application/calculations/__init__.py`
- `src/cadrumo/application/calculations/tests/test_row_set_assembly.py`

## Description

- Add the public snapshot-bound row-observation assembly command.
- Delegate to the existing closed grouping dispatcher with the selected revision and filing year.
- Preserve existing localized grouping and row-validation refusals without creating a source resolver, store, provenance carrier, or filing writer.
- Export the command from the calculation application facade and prove its snapshot-bound wiring.

## Outcome

`assemble_observations_for_snapshot` is the sole shared application command for
turning row-set cells into the existing typed observation union under the
law-selected registry snapshot. The command deliberately leaves source ownership,
row identity/fingerprint construction, row-to-casilla materialisation, and
encrypted revision persistence to the source-specific resolver and later
predecessor rows. It neither represents the Google pull report as calculation
ingress nor adds a parallel source authority.

## Notes

Vaultspec-RAG, whole-file reads, and exact-symbol search confirmed the existing
single source-mesh and encrypted-revision path: `CalculationSourceResolution`,
the live calculation action, and `persist_calculation_revision` already own the
row carriers. The focused test suite passed 25 tests; scoped Ruff, compilation,
and diff hygiene passed. The invalid-row and unknown-grouping cases prove the
new command preserves the established localized refusals.

Concurrent shared-worktree commit `8937f0cf548` captured the two production
files before this Step's scoped follow-on commit. This record assigns the
complete logical change to that implementation commit plus the follow-on test,
plan, execution-record, and feature-index commit; no history was rewritten and
no production file was duplicated.
