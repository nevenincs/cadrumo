---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:056ba61d3eaedd0f97e2eaa3d397e8f1ac3ddf520fc7641e79b7c409bdee1c12'
step_id: 'S211'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
