---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:c7110448133c491464f8634dd22a9993926c223b85f1d2f50ca9806e7752ff77'
step_id: 'S265'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only single-manifest load facade from IVA remote-state application code; make persistence tests use the injected repository's canonical load operation directly, retain live manifest listing and stored-evidence aggregation, run focused IVA acquisition gates, remeasure exact reachability, update cadence, and write the Step Record.

## Scope

- `IVA remote-state acquisition manifest load facade and tests`
- `focused acquisition persistence gates`
- `exact reachability`
- `cadence reference`
- `Step Record`

## Changes

- `M` `src/cadrumo/application/live/iva_remote_state.py`
- `M` `src/cadrumo/application/live/tests/test_iva_remote_state_acquisition.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/live/iva_remote_state.py src/cadrumo/application/live/tests/test_iva_remote_state_acquisition.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/live/tests/test_iva_remote_state_acquisition.py -k "manifest"` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Five focused encrypted-manifest persistence, redaction, active-profile, and identity-substitution tests pass through the canonical repository. Exact unused symbols improved from 280 to 279; 31 unreachable modules and zero orphaned tests remain.
