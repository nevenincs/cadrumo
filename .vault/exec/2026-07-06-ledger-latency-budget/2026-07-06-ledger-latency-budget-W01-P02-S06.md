---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:81b553cf5630a7210d8954f599123b665d6d37a1bfc981d542895d8769427ee7'
step_id: 'S06'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Pin timestamp witness drift detection

## Scope

- `src/aeat/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py`

## Description

- Search the code and vault records for the persisted transaction timestamp witness and double-parse residual.
- Read the transaction repository timestamp helpers and existing timestamp roundtrip drift tests before editing.
- Add a focused missing-`modified_at` test that exercises the decoded-row witness helper and the real repository load boundary.
- Run the file-level ruff check and the focused unit test.
- Audit the change and record that no open findings remain.

## Outcome

`test_transactions_repository_roundtrip.py` now pins the timestamp witness contract that takes an already decoded persisted envelope dict. The new test deletes `modified_at` from the decoded payload, proves `_validate_persisted_transaction_timestamps` rejects it directly, then persists the mutated envelope and proves `TransactionCatalogueRepository.load()` raises `StoredTransactionDriftError` instead of allowing default timestamp repair.

## Notes

No runtime code changed in this step. The focused ruff and unit test gates passed, and the rolling audit found no issues.
