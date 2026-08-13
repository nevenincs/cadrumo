---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:05463e01bf851a1100503ce7fcfca75ca431d96ba62cc8b55616f0492f03f5ea'
step_id: 'S17'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Define lifecycle journal, ordered event stream, owner lease, compare-and-swap revision, and secure reference ports

## Scope

- `src/cadrumo/application/operations/_journal.py`
- `src/cadrumo/application/operations/tests/test_journal.py`

## Description

- Retain the credential-free persisted snapshot, journal, event-stream, lease, and secure-reference boundary.
- Add a UTC-aware `started_at` fact to the persisted snapshot without changing the runtime `OperationSnapshot` contract.
- Derive persisted phase state from the final phase event, bind nonempty batches to the final event timestamp, and reject reversed event timestamps.
- Require a terminal snapshot to settle through one final terminal event carrying the exact terminal receipt.
- Exercise valid phase, no-phase, and terminal cases plus planted temporal, phase-drift, terminal-middle, and receipt-divergence failures with concrete operation models.

## Outcome

The journal persistence contract now preserves an ordered lifecycle record: phase state is event-derived, terminal settlement cannot be followed by more events, and the persisted timestamps agree with the event batch. The runtime snapshot and adapter policy remain unchanged.

## Verification

- `uv run --no-sync ruff check src/cadrumo/application/operations/_journal.py src/cadrumo/application/operations/tests/test_journal.py`
- `uv run --no-sync ruff format --check src/cadrumo/application/operations/_journal.py src/cadrumo/application/operations/tests/test_journal.py`
- `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_journal.py -q` - 12 passed
- `uv run --no-sync basedpyright src/cadrumo/application/operations/_journal.py src/cadrumo/application/operations/tests/test_journal.py` - 0 errors, 0 warnings, 0 notes
- Fresh independent S17 review - PASS, no findings in the journal contract or its direct tests.
- `uvx vaultspec-core vault check all` - exit 0; structural checks passed with 1,362 advisory shared-corpus warnings and no closure error.

## Notes

No adapter policy or runtime snapshot surface changed. The Step state was left untouched for the supervising executor.
