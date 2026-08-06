---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:326d509d00c64efdb64452fa652c81cb4bfc7c12620fbdd62f7f03485e0e09cc'
step_id: 'S68'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add the AST-structural provenance gate asserting the storage root is joined onto only inside declared producers, matching Path binops, joinpath, glob, rglob, and iterdir through any wrapping, and excluding docstring mentions and field-declaration sites from the walk, leaving a named pending-debt table for sites not yet taxonomy-governed

## Scope

- `src/cadrumo/tests/test_storage_provenance_gate.py`

## Description

- Add the AST-structural gate asserting `cadrumo_local_storage_root` is joined onto only inside declared producer functions, matching the join through `Path` binops, `joinpath`, `glob`, `rglob`, `iterdir`, and any `Path()` wrapper.
- Exclude docstring mentions and field-declaration sites from the walk.
- Leave a named pending-debt table for sites not yet taxonomy-governed.

## Outcome

Landed in commit `11f83f4319` (ADR R9). At landing, nine pending-debt entries remained; the two database-path entries are being closed by an in-progress peer lane (tracked as S72). The gate has a known blind spot for a local rebind of the root before joining, e.g. `root = settings.cadrumo_local_storage_root` then `root / "x"` (tracked as S80).

## Notes
