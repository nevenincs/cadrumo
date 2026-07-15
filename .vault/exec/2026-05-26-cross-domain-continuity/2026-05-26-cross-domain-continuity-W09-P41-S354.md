---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S354'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# R9-TOMAS-HIGH subenumerate domestic_exempt IvaCategory

## Scope

- `closed by 21cab5df0: IvaExemptionArticle is carried from Transaction through IvaLedgerCandidate/IvaLedgerObservation and optional ledger_iva_aggregation selectors`
- `with validation that article filters only apply to DOMESTIC_EXEMPT`
- `kept broad DOMESTIC_EXEMPT behaviour when no article is declared`
- `verified by IVA ledger and registry binding tests`
- `src/aeat/domain/iva/_schema.py src/aeat/domain/transactions/_models.py src/aeat/application/aggregation/_iva_ledger.py src/aeat/domain/calculations/registry/_ledger_bindings.py`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `21cab5df04` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
