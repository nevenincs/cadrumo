---
tags:
  - '#exec'
  - '#core-authority'
step_id: S90
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W10.P27.S90 - BLOCKED: reconciliation status triple is domain-divergent

## Outcome

BLOCKED. The three "reconciliation status" enums are domain-divergent intentional types
that MUST NOT be unified.

- `RentaReconciliationStatus` (domain/renta/_ledger_expenses.py:61): Two members —
  TRANSACTION_ONLY, LINKED_INVOICE. Tracks invoice-to-transaction deduplication state.
  Domain: renta ledger expense reconciliation (invoice vs. transaction linkage).

- `ReconciliationStatus` (application/filing/reconciliation/_schema.py:34): Three members —
  COINCIDE, DIVERGENTE, NOT_YET_FOUND. Filing draft vs justificante comparison verdict.
  Domain: AEAT submission reconciliation.

- `ModeloReconciliationVerdict` (application/modelo/_reconcile.py:41): Three members —
  MATCHES, MISMATCHES, EVIDENCE_INVALID. Modelo draft vs evidence comparison verdict.
  EVIDENCE_INVALID has no semantic counterpart in the other two enums.
  Domain: modelo evidence validation.

The tracker (MERGE-005) claimed "100% semantic: Spanish/English split" which is
incorrect. Only `ReconciliationStatus` and `ModeloReconciliationVerdict` have a
loose Spanish/English correspondence (COINCIDE=MATCH, DIVERGENTE=MISMATCH,
NOT_YET_FOUND=MISSING), and even these differ by EVIDENCE_INVALID.
`RentaReconciliationStatus` covers a completely unrelated concept.

Per the W04/W05 lesson: same-concept verification shows these are intentional
domain-specific enums. No consolidation warranted.

## Files touched

None — no code changes.

## Verification

N/A (no change).
