---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S36'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Add encrypted repository roundtrip coverage for validator JSON-mode loading

## Scope

- `src/aeat/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py`

## Description

- Attempt semantic grounding for encrypted repository JSON-mode validation coverage; record the unavailable service and timed-out fallback.
- Add a repository roundtrip test that persists a transaction built without an explicit `transaction_id`.
- Inspect the encrypted row's JSON envelope to prove storage-shaped string fields are present before load.
- Load through `TransactionCatalogueRepository.load()` and assert equality, derived id, and representative non-default fields.

## Outcome
- `src/aeat/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py` now covers validator JSON-mode loading through the encrypted repository boundary.
- `uv run ruff check src/aeat/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py` passed.
- `uv run pytest -q -n 0 src/aeat/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py::test_transaction_catalogue_load_uses_json_mode_for_derived_id_roundtrip` passed.

## Notes

- `uv run vaultspec-rag search "encrypted repository roundtrip transaction validator JSON-mode loading test" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads of existing encrypted repository roundtrip tests.
