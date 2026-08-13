---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:fbe90d65e48f48237efeaf42e0e04ab86307522da9db550e0d54573a3c8c4755'
step_id: 'S05'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---
# `P02.S05` - Sweep the IvaLedgerObservation fixture builders to declare the deduction authority the real projection carries, deriving it from the invoice classification path rather than choosing a kind that makes the test pass

Scope: `src/cadrumo/domain/calculations/registry/tests/`.

## Description

- Derive fixture evidence authority from the production deduction-kind mapping.
- Supply the legal deduction kind and evidence locator on real input-IVA fixtures.
- Preserve the production exemption for recargo-equivalencia observations.
- Replace an impossible negative selector row with a production-reachable domestic reverse-charge row.

## Outcome

The fixture sweep now carries the same exact deduction authority enforced by production without duplicating its kind-to-authority table. The focused ledger aggregation lane passed forty-seven tests after the repair. The additional registry fixture lane passed fifty-six owned tests; three pre-existing Modelo 390 export-position failures remain owned by P03.S13 and are not part of this step. The exact repaired selector node passed.

Ruff check and format check passed. BasedPyright reported zero errors, warnings, or notes. Scoped diff checking passed.

## Notes

The first review found one high-severity impossible-fixture defect in the negative AIC selector row. That row was corrected and the exact test rerun green. No alternative Git index was used. No plan or test expectation was weakened.
