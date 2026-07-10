---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S35'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Add tampered transaction id rejection coverage for storage-shaped JSON

## Scope

- `src/aeat/domain/transactions/tests/test_models.py`

## Description

- Attempt semantic grounding for tampered transaction id JSON coverage; record the unavailable service and timed-out fallback.
- Add a JSON-mode test that serializes a real transaction, mutates only `transaction_id`, and validates the tampered JSON payload.
- Assert the after-validator rejects the tampered id with the derived-id mismatch message.

## Outcome
- `src/aeat/domain/transactions/tests/test_models.py` now covers storage-shaped JSON transaction id tampering.
- `uv run ruff check src/aeat/domain/transactions/tests/test_models.py` passed.
- `uv run pytest -q -n 0 src/aeat/domain/transactions/tests/test_models.py::test_transaction_json_rejects_tampered_derived_id_in_storage_payload` passed.

## Notes

- `uv run vaultspec-rag search "tampered transaction id rejection storage-shaped JSON transaction model test" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads and `rg` results for existing model and repository tamper tests.
