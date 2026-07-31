---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:36368ed29d348ad8b7c6d78c6b35e5fadb1b1f492a717a03d078ee5d0b75c740'
step_id: 'S20'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Content-pin derive_filing_record_id to the filing outcome of work_unit_id, calculation_revision_id, filed_by, and member_nif, dropping filed_at from the identity while retaining filed_at as a non-identity last-seen body field, and update the ModeloRecord model validator to re-check the outcome-pinned id

## Scope

- `src/aeat/domain/modelos/_filing_record.py`

## Description

- Drop `filed_at` from `derive_filing_record_id`: the id now content-addresses the filing outcome (`work_unit_id`, `calculation_revision_id`, `filed_by`, and `member_nif` for member-scoped group filings).
- Update the `ModeloRecord` model validator to re-derive the outcome-pinned id; `filed_at` stays a non-identity last-seen body field.
- Sweep every `derive_filing_record_id` call site (3 production: filing persistence, external import, amendment; plus 13 fixture/support files) to drop the `filed_at` argument via an AST-aware rewrite that left `ModeloRecord(...)` constructions (which keep `filed_at`) untouched. No back-migration.

## Outcome

Landed in commit `386618a68`. A re-file of the same revision by the same actor now resolves to the same record id; 42 filing-surface tests green.

## Notes

Co-committed with `S21` (the no-op consumes this identity). Chose to remove `filed_at` from the signature (not keep it as an ignored parameter) for a clean contract, after confirming all 18 caller files were free of peer WIP. A pre-existing `ty` diagnostic on the untouched `ModeloRecordStatus` default-assignment line is not part of this change.
