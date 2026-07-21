---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S34'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Add transaction JSON roundtrip coverage for non-default fields and derived ids

## Scope

- `src/aeat/domain/transactions/tests/test_models.py`

## Description

- Attempt semantic grounding for transaction JSON roundtrip coverage; record the unavailable service and timed-out fallback.
- Add a focused JSON-mode transaction roundtrip test that omits `transaction_id` on construction.
- Assert the derived id before and after JSON roundtrip.
- Assert representative non-default fields survive the roundtrip.

## Outcome
- `src/aeat/domain/transactions/tests/test_models.py` now covers the S31 derived-id default under a non-default transaction payload.
- `uv run ruff check src/aeat/domain/transactions/tests/test_models.py` passed.
- `uv run pytest -q -n 0 src/aeat/domain/transactions/tests/test_models.py::test_transaction_json_roundtrip_preserves_non_default_fields_and_derived_id` passed.

## Notes

- `uv run vaultspec-rag search "transaction JSON roundtrip non-default fields derived transaction id tests" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads of existing transaction model tests.
