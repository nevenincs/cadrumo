---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S30'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# C4-1 Extract the common base payload and have the review payload extend it, keeping serialized JSON byte-identical

## Scope

- `src/aeat/application/ledger/_models.py`

## Description

- Confirmed the conformance gate checks field-set + validation, not key order,
  and consumers read by key — so subclassing (which appends `review_status`) is
  shape-safe despite `review_status` having been mid-list in the duplicate.
- Made `LedgerTransactionReviewPayload` subclass `LedgerTransactionPayload`,
  adding only `review_status`; it now inherits the ~25 fields, the
  `source_jurisdiction` validator, and the strict-frozen config.
- Delegated the `ledger_transaction_review_payload` builder to
  `ledger_transaction_payload` via `model_dump()` (`TransactionId` is an
  `Annotated` str, so the strict re-validation round-trips).

## Outcome

Committed as `344c1311a`, tagged `relocation:LedgerTransactionReviewPayload`
(2 files, +8/-69). Ruff clean; full `test_json_schema_conformance.py` plus the
whole `application/ledger` suite (298 tests) green, including the
report-to-payload mirror harness and the interface-contract payload tests.

## Notes

The CLI-layer OutputSchema mirror in `_ledger_payloads.py` is left intact: it is
the deliberate app/CLI boundary mirror the conformance harness exists to police,
not duplication to collapse.
