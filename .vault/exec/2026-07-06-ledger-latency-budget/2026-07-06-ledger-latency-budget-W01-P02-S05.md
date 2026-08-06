---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:52b1cb970f8b0dad8506d1931ab2d940c296721b035135283fbb14b594a9d5f3'
step_id: 'S05'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Pin unchanged-row save reconciliation

## Scope

- `src/aeat/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py`

## Description

- Search the code and vault records for the per-transaction save reconciliation and unchanged-row skip contracts.
- Read the transaction repository roundtrip tests, repository reconciliation code, and secure-object raw metadata surface before editing.
- Add a real roundtrip test that compares secure-object revision metadata before and after changing only one transaction row.
- Run the file-level ruff check and the focused unit test.
- Audit the change and record that no open findings remain.

## Outcome

`test_transactions_repository_roundtrip.py` now proves that saving a catalogue with one changed transaction does not re-encrypt or upsert an unchanged transaction row. The test reads real secure-object raw metadata, changes one transaction without changing its derived id, and asserts the unchanged row keeps the same `revision_id`, `payload_hash`, and `ciphertext_hash` while the changed row records a new revision linked to the prior payload.

## Notes

No runtime code changed in this step. The focused ruff and unit test gates passed, and the rolling audit found no issues.
