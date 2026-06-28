---
step_id: S269
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W02.P11.S269 — SnapshotNotFoundError AeatError enrollment

## Scope

Change `class SnapshotNotFoundError(KeyError)` to
`class SnapshotNotFoundError(AeatError, KeyError)` at
`src/aeat/application/live/_snapshot_base.py:49` so the base is enrolled
in `ERROR_REGISTRY` via `AeatError.__init_subclass__`.

## Outcome

### Base class changed

`SnapshotNotFoundError` now inherits `(AeatError, KeyError)`. The `AeatError`
import was added to `_snapshot_base.py`.

### Registry entry

`aeat.application.live._snapshot_base.SnapshotNotFoundError` registered in
`src/aeat/core/errors/registry/_application.py` with:
- code: `FAIL_SNAPSHOT_NOT_FOUND`
- category: `FAIL`
- message_key: `errors.fail.fail_snapshot_not_found`

### Per-service subclasses updated

The four per-service subclasses (`BorradorSnapshotNotFoundError`,
`CensoSnapshotNotFoundError`, `ExpedientesSnapshotNotFoundError`,
`NotificationsSnapshotNotFoundError`) previously declared
`(AeatError, SnapshotNotFoundError)` which now violates C3 linearization.
All four updated to `(SnapshotNotFoundError,)` — `AeatError` is already
in the MRO via the base. Their unused `AeatError` imports were removed.

## Locale keys

`errors.fail.fail_snapshot_not_found` added to all locale files.

## Files touched

- `src/aeat/application/live/_snapshot_base.py`
- `src/aeat/application/live/_borrador_100.py`
- `src/aeat/application/live/_censo.py`
- `src/aeat/application/live/_expedientes.py`
- `src/aeat/application/live/_notifications.py`
- `src/aeat/core/errors/registry/_application.py`
- `src/aeat/locales/*.yml`

## Test outcome

`pytest src/aeat/application/live/test_snapshot_base.py` — 26 passed, 0 failed.

## Collision signal

`git diff -- <target files>` before edits: no output (clean).
