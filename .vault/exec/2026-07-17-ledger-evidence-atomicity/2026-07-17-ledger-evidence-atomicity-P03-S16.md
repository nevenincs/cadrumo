---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S16'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Move the one-evidence-writer guard from the wrapper to the transaction builder so the bulk-classify path cannot bypass the attach authority: the builder asserts the evidence set equals the current evidence unless the _evidence_authority marker is present, OR prove BULK_CLASSIFY_ALLOWED_COLUMNS never intersects the evidence fields, with a gate proving bulk-classify cannot mutate any evidence field outside attach

## Scope

- `src/cadrumo/application/ledger/_actions_manual.py`
- `src/cadrumo/application/ledger/_actions_classification.py`
- `src/cadrumo/application/ledger/_models.py`

## Description

- Take the second (gate) option from the step: prove `BULK_CLASSIFY_ALLOWED_COLUMNS` never intersects the evidence field set.
- Add `test_bulk_classify_columns_never_carry_evidence_fields` asserting `BULK_CLASSIFY_ALLOWED_COLUMNS & _EVIDENCE_PATCH_FIELDS == ∅`, so the builder-direct bulk-classify path can never carry `purchase_invoice_evidence_id` / `attachment_ids` and thus cannot bypass the attach authority.

## Outcome

- The one-evidence-writer guard is now defended at the bulk path too: bulk classify reaches `_prepare_manual_transaction_update` directly (bypassing the wrapper guard) but is structurally unable to name an evidence column. Landed in commit `b3d8ab6b76` (reviewer LOW-1). Ledger application suite green.

## Notes

- Chose the disjointness gate over relocating the guard into the builder: it is the cheaper, self-enforcing option the step permits and it keeps the builder's signature unchanged for the split writer that also composes it.
