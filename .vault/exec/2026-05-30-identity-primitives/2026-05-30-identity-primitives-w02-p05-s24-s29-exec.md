---
step_id: S24
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W02.P05.S24-S29 — promote SnapshotId

## Scope

Declare the hex-64 `SnapshotId` typed alias in
`src/aeat/core/identity/_snapshot.py` per ADR Rule 6 clause (a),
re-export through the package `__init__`, and lift the hex-64
`snapshot_id` BaseModel fields on the persisted live-notifications
and live-expedientes snapshot surfaces onto the alias.

## Outcome

`SnapshotId = Annotated[str, StringConstraints(min_length=64,
max_length=64, pattern=r"^[0-9a-f]{64}$")]` declared in
`src/aeat/core/identity/_snapshot.py` and exported through
`aeat.core.identity.__all__`.

Promoted BaseModel fields:

- `src/aeat/application/live/_notifications.py`:
  `PersistedNotificationsSnapshot.snapshot_id`.
- `src/aeat/application/live/_expedientes.py`:
  `PersistedExpedientesSnapshot.snapshot_id`.

Real-behavior tests added at
`src/aeat/core/identity/test_snapshot.py` cover acceptance of a
canonical sha-256 hex digest, rejection of uppercase hex, rejection
of short/long values, and rejection of non-hex characters.

## Genuine non-canonical fields skipped

- `src/aeat/application/user_profile/_censo_sync.py:88,111`
  (`CensoProfileComparison.snapshot_id`, `CensoApplyResult.snapshot_id`)
  — constraint is `Field(min_length=1)` with no upper bound and no
  hex shape. The census snapshot id is derived by
  `derive_snapshot_id_from_json` (not by `hashlib.sha256` directly);
  the resulting string is not a hex-64 digest. Promoting to
  `SnapshotId` would reject every census snapshot at construction.
  Genuine non-canonical reference; skipped per the brief's
  "genuine non-canonical model field" clause.
- `src/aeat/application/live/_censo.py:107`
  (`CensoSnapshot.snapshot_id: str = Field(min_length=1,
  max_length=128)`) — same census family; not hex-64.
- `src/aeat/application/user_profile/__init__.py:248,265`
  (`ProfileSnapshot.snapshot_id`, `ProfileStaleCheckReport.snapshot_id`)
  — constraint is `Field(min_length=1, max_length=128)`. Profile
  snapshots are minted by `new_profile_snapshot_id` which composes a
  ``{profile_id}:{timestamp}:{uuid4hex}`` string — not hex-64.
  Genuine non-canonical reference; skipped.

## Verification

- `uv run --no-sync pytest src/aeat/core/identity/test_snapshot.py`
  returns `5 passed`.
- `uv run --no-sync pytest src/aeat/application/live/` returns
  `122 passed` with `1 deselected`; both `PersistedNotificationsSnapshot`
  and `PersistedExpedientesSnapshot` round-trip and de-duplication
  paths exercise the alias.

## Plan steps closed

`W02.P05.S24`, `S25`, `S26`, `S27`, `S28`, `S29`. The S29 dedicated
roundtrip test would duplicate the existing
`test_notifications.py` and `test_expedientes.py` boundary coverage
that already exercises persistence and reload through the real
adapter; the typed alias is now exercised on every test that
constructs the persisted snapshot. No additional standalone
roundtrip module added.
