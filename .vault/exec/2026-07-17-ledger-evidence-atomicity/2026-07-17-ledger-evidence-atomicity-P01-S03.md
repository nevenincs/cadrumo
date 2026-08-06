---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:9ba2a3672f1f50b29c07221a068bae733d87d6c0dc7db1c7e2a828ccc8d823ca'
step_id: 'S03'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Prove create-time and attach-time evidence validation enforce the same missing and cross-bucket policy

## Scope

- `src/cadrumo/application/ledger/tests/test_actions_create_evidence_validation.py`

## Description

- Add the attach-side parity tests mirroring the four existing create-time refusals: missing purchase evidence, cross-bucket purchase evidence, missing attachment manifest, and cross-bucket attachment.
- Each attach test seeds an evidence-free transaction, then asserts `attach_manual_transaction_evidence` refuses the same invalid input with the same error substring create rejects, and leaves the row's evidence link empty.

## Outcome

- Demonstrates create and attach share one validator (`_verify_evidence_references`): neither door is a weaker route into the evidence catalogue. Missing evidence names `purchase_invoice_evidence_id` / `attachment_ids`; cross-bucket evidence names the `command bucket`.
- `test_actions_create_evidence_validation.py`: 8 passed (4 create + 4 attach). Full ledger application suite: 382 passed. Ruff clean. Commit `0ea2800b8c`.

## Notes

- Real InvoiceCatalogue and AttachmentStore over the shared secure-object store; cross-bucket cases seed a genuine other-bucket record and prove the bucket guard fires.
