---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S11'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# Implement explicit persisted M210 transaction classification plus its operator write surface, runtime tipo-renta source context, Spanish-source classifier, and resolver with typed foreign, unresolved, and incomplete-classification issues

## Scope

- `src/aeat/domain/transactions + src/aeat/entrypoints/cli + src/aeat/application/modelo + src/aeat/application/aggregation`

## Description

- Persist explicit M210 income classification beside the transaction, including raw official code, gross amount, rate, payer mode and identity, and property/right identity.
- Add direct `ledger classify` M210 operator options and reject incompatible automatic or split classification modes.
- Admit only active incoming Spanish-source observations, retain Article 13.1 territorial evidence with the Article 24 base, and emit typed foreign, unresolved, and incomplete-classification issues.

## Outcome

The source resolver never infers an M210 official code from `irpf_category`; it uses the operator's persisted classification and preserves the row facts needed by 0A. Manual and ledger authority are recorded on the calculation revision and identity. Landed in `8f5f690ed0`.

## Notes

The raw-code/formula-token guard now applies in both manual and ledger source modes.
