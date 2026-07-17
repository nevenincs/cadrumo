---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S38'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Run the transaction repository tests after the validator rewrite

## Scope

- `src/aeat/adapters/persistence/profile/tests`

## Description

- Re-ground the repository validator boundary through semantic code and vault search.
- Read the encrypted transaction repository and profile persistence test directory before running the gate.
- Run the full profile persistence test directory after the validator rewrite.
- Repair the date-index moved-transaction fixture so it rebuilds through `Transaction.model_validate` with no stale explicit id.
- Run focused ruff and pytest checks for the repaired date-index test.
- Re-run the full profile persistence test directory.

## Outcome
- `src/aeat/adapters/persistence/profile/tests/test_transaction_date_index.py` no longer constructs an invalid moved transaction through unchecked `model_copy`.
- The first full `src/aeat/adapters/persistence/profile/tests` run failed only `test_date_index_updates_when_filing_date_changes`.
- `uv run ruff check src/aeat/adapters/persistence/profile/tests/test_transaction_date_index.py` passed.
- `uv run pytest -q -n 0 src/aeat/adapters/persistence/profile/tests/test_transaction_date_index.py::test_date_index_updates_when_filing_date_changes` passed.
- `uv run pytest -q -n 0 src/aeat/adapters/persistence/profile/tests` passed: 104 passed in 16.19s.

## Notes

- Semantic code search returned `src/aeat/adapters/persistence/profile/transactions.py` and the encrypted repository roundtrip tests. Semantic vault search returned the current latency plan/research and prior validator exec records.
- The failed fixture was stale under the content-addressed transaction id invariant: changing `raw.booked_date` and `raw.value_date` changes the derived id, so the test must omit the old id and let the model derive the replacement id.
