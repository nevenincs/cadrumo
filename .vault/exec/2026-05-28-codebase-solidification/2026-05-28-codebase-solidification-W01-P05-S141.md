---
step_id: S141
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P05.S141 — canonical `_now` in `aeat.core.time._clock`

## Outcome

Created `src/aeat/core/time/_clock.py` exporting `_now() -> datetime` (returns
`datetime.now(tz=UTC)`) and extended `src/aeat/core/time/__init__.py` to
re-export it. Migrated six local `_now` / `_utcnow` copies to import the
canonical function; deleted all six local definitions. The `_engine.py` local
was named `_utcnow`; the canonical import was aliased as `_utcnow` to avoid
touching the dozens of interior call-sites.

## Files touched

- `src/aeat/core/time/_clock.py` (created)
- `src/aeat/core/time/__init__.py` (re-export added)
- `src/aeat/application/ledger/_business_operation_invoice.py` (local `_now` deleted)
- `src/aeat/application/ledger/_evidence.py` (local `_now` deleted)
- `src/aeat/application/live/_expedientes.py` (local `_now` deleted)
- `src/aeat/application/live/_notifications.py` (local `_now` deleted)
- `src/aeat/application/live/_verify.py` (local `_now` deleted)
- `src/aeat/application/workflow/_engine.py` (local `_utcnow` deleted; aliased import)

## Collision check

`git diff` on all target files returned empty output before first edit — no
peer WIP in scope.

## Test outcome

48/48 passed: `uv run --no-sync pytest src/aeat/core/time/ src/aeat/application/workflow/test_engine.py -x -q`
