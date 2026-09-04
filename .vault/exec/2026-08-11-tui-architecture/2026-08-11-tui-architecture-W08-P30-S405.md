---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:82bba79d4484e1a0140db30267892b92274331b8bd4af70e427089d46757066c'
step_id: 'S405'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give the Ledger workspace the review fixtures every other principal surface already has. MEASURED 2026-09-04: the fixture registry declares 54 specs covering home (5 states), workbench-root (3), declarations-* (17), aeat-sync-* (27) and operation-modal (1), and NOT ONE for Ledger -- the word appears twice in that module, incidentally. Ledger is the one principal workspace whose screens can be reached only through a live installed session, so its overview, entries, review, import, classification, evidence and reconciliation surfaces have no ready, empty, blocked, stale, unavailable, validation, confirmation or failure reading at all. Build them from the same immutable non-sensitive projection shape the sibling fixtures use; do not reach a repository.

## Scope

- `src/cadrumo/entrypoints/tui/devtools/workbench_fixtures.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/devtools/workbench_fixtures.py`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/tui/devtools/tests/test_workbench_fixtures.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/tui/tests` -> `pass`

## Notes

The classification area has no empty reading and is registered only in the populated
states. Its controller refuses a target the visible projection does not carry, which is
the correct refusal; fabricating a selection over rows that do not exist would have made
the fixture a stand-in rather than a reading.

Observed while building it, not fixed here: `LedgerWorkspaceController.classification_target_coordinate`
raises `RuntimeError` when no target is bound, rather than returning a typed refusal the
screen can render. Nothing in production reaches it that way today because the only
caller selects a row first, but a host composing the area directly would crash rather
than refuse.
