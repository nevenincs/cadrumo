---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:1dfe87eadb740ce0dce34c071b15b967a58f793d90cf6b6e19da894fa7c796e5'
step_id: 'S211'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only byte-derived and non-identity notification-document field inventories and their persisted-field classification test/imports from production custody, while retaining the caller-supplied live comparison authority and focused behavioral proofs for idempotent re-store, divergence refusal, timestamps, and parsed-document custody.

## Scope

- `Notification-document custody and focused service tests`
- `exact reachability signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/application/live/notification_documents.py`
- `M` `src/cadrumo/application/live/tests/test_notification_documents_service.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/live/notification_documents.py src/cadrumo/application/live/tests/test_notification_documents_service.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m "" --basetemp <isolated-workspace-temp> <four focused notification custody retry/divergence tests>` -> `pass` (4 passed)
- `verify:` `rg -n "_BYTE_DERIVED_FIELDS|_NON_IDENTITY_FIELDS" src/cadrumo --glob '*.py'` -> `pass` (no matches)
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `findings` (315 exact unused symbols; both target inventories absent)

## Notes

The exact unused-symbol count fell from 317 immediately before S211 to 315 after removal of the two field-partition inventories. Concurrent peer changes also moved the graph from 65 to 63 unreachable modules, 18 to 15 orphaned tests, and 2094 to 2092 shipped modules while reachable modules remained 2028; those aggregate changes are not attributed to S211.
