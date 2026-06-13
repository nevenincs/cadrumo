---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S09'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Evidence Row Magnitudes

## Scope

Step `P03.S09`.

## Description

- Added non-negative validation for `LedgerEvidenceRow.amount`.
- Kept `value_in_eur` under the same magnitude validator.
- Updated evidence-row field documentation.

## Outcome

Ledger filing evidence mirrors the transaction magnitude convention.

## Notes

The evidence row continues carrying `direction`, legal refs, and source refs.
