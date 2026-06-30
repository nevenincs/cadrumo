---
generated: true
tags:
  - '#index'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - '[[2026-06-30-ledger-add-idempotency-P01-S01]]'
  - '[[2026-06-30-ledger-add-idempotency-P01-S02]]'
  - '[[2026-06-30-ledger-add-idempotency-P01-S03]]'
  - '[[2026-06-30-ledger-add-idempotency-P03-S08]]'
  - '[[2026-06-30-ledger-add-idempotency-P03-S09]]'
  - '[[2026-06-30-ledger-add-idempotency-P03-S10]]'
  - '[[2026-06-30-ledger-add-idempotency-adr]]'
  - '[[2026-06-30-ledger-add-idempotency-plan]]'
  - '[[2026-06-30-ledger-add-idempotency-research]]'
---

# `ledger-add-idempotency` feature index

Auto-generated index of all documents tagged with `#ledger-add-idempotency`.

## Documents

### adr

- `2026-06-30-ledger-add-idempotency-adr` - `ledger-add-idempotency` adr: `manual ledger add idempotency and verify-report retry shape` | (**status:** `accepted`)

### exec

- `2026-06-30-ledger-add-idempotency-P01-S01` - Add an existence check in create_manual_transaction so a same-key add whose content matches the stored row returns the existing-row quintet as a no-op, emitting no second LEDGER_TRANSACTION_CREATED event, leaving created_at and modified_at unchanged, and skipping evidence re-verification, modelled on create_work_unit
- `2026-06-30-ledger-add-idempotency-P01-S02` - Raise an instructive localised conflict error when a stored row exists for the same idempotency key but the command content differs, naming the conflicting field set
- `2026-06-30-ledger-add-idempotency-P01-S03` - Signal the no-op structurally on the result by returning the existing-row quintet with empty bucket_event_ids, preserving the uniform ledger mutation quintet shape
- `2026-06-30-ledger-add-idempotency-P03-S08` - Change derive_verification_report_id to fold the verification outcome of calculation_revision_id, completeness_status, the findings tuple, and verified_by, and drop run_at from the identity
- `2026-06-30-ledger-add-idempotency-P03-S09` - Update the VerificationReport model validator to re-check the new outcome-pinned id derivation and retain run_at as a non-identity last-seen body field
- `2026-06-30-ledger-add-idempotency-P03-S10` - Confirm verify_modelo_revision upserts the outcome-pinned report in place so a non-granting retry collapses to one report while the granting path stays self-limiting

### plan

- `2026-06-30-ledger-add-idempotency-plan` - `ledger-add-idempotency` plan

### research

- `2026-06-30-ledger-add-idempotency-research` - `ledger-add-idempotency` research: `manual ledger add idempotency and verify-report retry shape`
