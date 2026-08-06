---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:48dadbcdbefe9e236e8ba3eac7d07dca71146ecae3cf13bb74f55b652e8d37ae'
step_id: 'S02'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Prove direct evidence patches fail, invoice linkage cannot mutate evidence, and failed attach or link leaves transaction, evidence catalogue, provenance, and event history unchanged

## Scope

- `src/cadrumo/application/ledger/tests/test_actions_update_evidence.py`

## Description

- Prove the generic command door refuses a direct evidence change (`update_manual_transaction` with an evidence-bearing command raises, names `aeat app ledger attach`, and leaves the row evidence-free with only the CREATED event).
- Prove the generic patch door refuses an evidence-field patch (`update_manual_transaction_fields`).
- Prove a non-evidence edit on an evidenced row succeeds and preserves the evidence verbatim.
- Prove `link_manual_transaction_invoice` does not mutate evidence: it links the invoice bidirectionally while leaving the transaction's evidence link and the bucket event history unchanged.
- Prove failed attach (unknown evidence id) leaves the transaction, provenance, and event history unchanged.
- Prove failed invoice link (unknown invoice id) leaves the transaction and event history unchanged.

## Outcome

- Real secure storage, real repositories, real bucket-event history; no mocks/stubs/monkeypatch. Every atomicity proof forces a refusal and asserts the on-disk state and event history are unchanged.
- `test_actions_update_evidence.py`: 7 passed. Full ledger application suite: 382 passed. Ruff clean. Commit `9296e3ebd2`.

## Notes

- The atomicity of a refused attach/link holds structurally: `_verify_evidence_references` and the invoice missing/cross-bucket guard both run before any `_save_transaction_catalogue_and_events` / catalogue write, so no partial write is reachable on the refusal path.
