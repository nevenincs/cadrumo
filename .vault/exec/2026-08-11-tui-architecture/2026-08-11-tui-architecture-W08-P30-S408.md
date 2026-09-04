---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:9dd0fc103ae20d3c91524fd3e7ac7a52e4c8eb9fed8f89fa3559716c7289b1d2'
step_id: 'S408'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give AEAT Sync its local row readers, or state per zone why the local authority cannot be read. The installed workspace projects overview rows only: census, filed-declaration, notification, evidence-comparison and reconciliation rows have no installed reader, so LOCAL_PROFILE and LOCAL_FILINGS report observable counts beside zones that carry no rows, while LOCAL_NOTIFICATION_CUSTODY and LOCAL_RECONCILIATION are UNAVAILABLE outright. The refusals are honest today; a workspace whose local side is permanently empty is not the target state.

## Scope

- `src/cadrumo/application/aeat_sync/workspace_reader.py`

## Changes

- `M` `src/cadrumo/application/aeat_sync/workspace_reader.py`
- `M` `src/cadrumo/application/workbench_generation.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/aeat_sync src/cadrumo/application/tests/test_workbench_generation.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" src/cadrumo/entrypoints/tui/tests/test_installed_workbench.py src/cadrumo/entrypoints/tui/aeat_sync` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.types` -> `pass`

## Notes

PARTIAL: one of five zones. Filed declarations now carry the local side the session already
holds -- FILED with its real filing time -- while the AEAT observation and the justificante
stay NOT OBSERVED, which the row model itself enforces: a receipt cannot be confident about
a submission nobody has looked for. Rows are deduplicated to the latest filing per natural
address, because a superseded record and its replacement describe one declaration and the
projector rejects duplicate addresses.

The remaining four are not deferred work items, they are genuinely uncapturable before a
pull. Notifications exist only at the AEAT. Evidence comparison and reconciliation are joins
that need the AEAT side to exist at all. Census would need a local-field-to-census-path
taxonomy that does not exist and that this step would have had to invent.
