---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:86df6d75237bc9985d3a7f02c76459b8a6a4308121c7919d1f5a45660c0d2017'
step_id: 'S185'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only cotejo_view_url builder and remove the declarations URL primitive name census that pins implementation identities; retain landed-origin behavior and live listing/document URL builder coverage, then remeasure the exact unused-symbol signal.

## Scope

- `declarations fetch URL primitives`
- `recorded-origin tests`
- `live reachability measurement`

## Changes

- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/_declarations_fetch.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_recorded_origin.py`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_recorded_origin.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_pdf_response_contract.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/outbound/aeat/sede/_declarations_fetch.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_recorded_origin.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail`
