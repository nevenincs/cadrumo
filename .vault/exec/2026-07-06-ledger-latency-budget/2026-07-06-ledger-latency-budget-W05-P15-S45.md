---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S45'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Confirm secure-object batch read removes repeated session setup from partition reads

## Scope

- `src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part3.py`

## Description

- Ground secure-object batch-read coverage with semantic search for `SecureObjectRepository load_many batch read partition read session setup tests`.
- Inspect `SecureObjectRepository.load_many`, `iter_many_with_failures`, `TransactionCatalogueRepository.partition_by_date_range`, and `_load_transactions_by_ids`.
- Confirm storage `load_many` performs one targeted `object_key IN` select and transaction partition reads call that batch path once for in-window rows.

## Outcome
- `uv run pytest -q -n 0 src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part3.py` passed: 12 tests in 1.08s.
- `uv run pytest -q -n 0 src/aeat/adapters/persistence/profile/tests/test_transaction_date_index.py::test_partition_by_date_range_uses_one_targeted_secure_object_batch` passed: 1 test in 0.72s.
- No runtime change was required for this residual confirmation step.

## Notes

- The storage contract compares `load_many` results to repeated single loads while asserting exactly one targeted secure-object `IN` select.
- The partition contract permits one point secure-object lookup for the encrypted membership index and asserts the transaction rows are read through exactly one batch select.
