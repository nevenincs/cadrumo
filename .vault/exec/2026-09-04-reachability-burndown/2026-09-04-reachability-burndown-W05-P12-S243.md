---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:f688b7aa5cdf35e920b0ed9b166c0fd29179a4b0534b31cb970b2fffd044a668'
step_id: 'S243'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the ownerless require_verified_aeat_session branch now that live reads are governed solely by ensure_authenticated_aeat_session.

## Scope

- `Preserve the application-auth custody boundary`
- `run focused auth gates`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record.`

## Changes

- `M` `src/cadrumo/application/auth/sessions.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/auth/sessions.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/application/auth/tests/test_clave_credential_resolution.py src/cadrumo/application/auth/tests/test_blank_profile_identity_refusal.py src/cadrumo/application/auth/tests/test_live_provider_kind_resolution.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact zero-target detector remains red on the remaining live population: 51 unreachable modules, 1 type-only module, 295 unused symbols, and 4 orphan tests. The configured parallel full-auth run was not attributable evidence because shared scratch cleanup and lock races produced 163 setup errors; the three focused owning suites passed serially (27 tests).
