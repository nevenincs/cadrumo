---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:ad9d4477ddffc05b272a2289b8a525bfbe84df877c98d07a50e01b0a2bfb94a0'
step_id: 'S133'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Implement edit admission, registry-backed schema projection, locale-neutral parsing, typed-intent normalization, and preflight services that issue exact ModeloEditBaselineV1 coordinates and never treat a Workspace safe-read baseline as mutation authority

## Scope

- `src/cadrumo/application/modelo/_edit_services.py`

## Changes

- `A` `src/cadrumo/application/modelo/_edit_services.py`
- `A` `src/cadrumo/application/modelo/tests/test_edit_services.py`
- `M` `src/cadrumo/application/modelo/_edit_models.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_models.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_edit_models.py -q -n 0 -m integration` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/_edit_services.py src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_edit_models.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/_edit_services.py src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_edit_models.py` -> `pass`

## Notes

`_edit_models.py` (S132) required two amendments discovered while implementing
the parse service: `ModeloEditParseRequestV1` now carries the full `baseline`
rather than an opaque `baseline_id` (the contract mints no server-side
baseline store), and `ModeloEditWritableScalarSurfaceEntryV1` gained a
`data_type` field so the parser can select its grammar. `test_edit_models.py`
updated to match.
