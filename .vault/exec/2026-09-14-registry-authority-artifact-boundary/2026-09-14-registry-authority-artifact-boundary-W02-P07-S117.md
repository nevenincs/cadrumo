---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:639f3011a7be524e5a4da557c6e6544024b1af3b34b7d582a7ce1060f717d267'
step_id: 'S117'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Run checkpoint B once on the integrated authority/profile/filing contract selection plus focused import, lint and type checks; repair only observed failures

## Scope

- `src/cadrumo`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/conftest.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py`
- `M` `src/cadrumo/domain/iva/classification.py`
- `M` `dev/registry/tests/test_authority_artifact_round_trip.py`
- `M` `dev/registry/tests/test_authority_publication.py`
- `verify:` `checkpoint B focused authority/profile/filing selection (69 passed)` -> `pass`
- `verify:` `compileall plus focused Ruff and ty checks` -> `pass`

## Notes

Checkpoint B was reopened on 2026-09-14 after the later integrated consumer cohort produced 32 passes and six stale usage-ratio fixture failures. The repaired fixture and source-window regressions await one affected-cohort run after receipt-covered compiler inputs are handed off.
