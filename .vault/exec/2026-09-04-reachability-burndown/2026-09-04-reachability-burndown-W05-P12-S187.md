---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:e50a5123de5292ff6f10e37be196600b7a2fe6f2b05c3c5228f7dac5301faed4'
step_id: 'S187'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only notification summary fetch-and-parse surface, including its summary-only type and parser branches, while preserving the live summary warm-up request and marker validation; migrate the shared auth-state refusal test to fetch_notifications_query, and confirm the application pull path remains query-owned.

## Scope

- `notifications adapter fetch/parser facade`
- `auth and navigation tests`
- `live notification application ownership`
- `exact reachability signal`

## Changes

- `M` `src/cadrumo/adapters/outbound/aeat/sede/notifications.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_auth_state.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_notifications.py`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/outbound/aeat/sede/tests/test_auth_state.py::test_fetch_notifications_query_carries_translated_message_on_none_path src/cadrumo/adapters/outbound/aeat/sede/tests/test_notifications.py src/cadrumo/application/live/tests/test_notifications.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/outbound/aeat/sede/notifications.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_notifications.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_auth_state.py` -> `pass`

- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail`
- `verify:` independent S187 re-review -> `pass`
