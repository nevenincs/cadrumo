---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S16'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

# add a reconciliation predicate that flags any divergence between the M390 ledger cuota-deducible-total and the reconciliacion-303 total, covering the import and reverse-charge flows

## Scope

- `src/aeat/_data/registry/aeat/modelos/390/`

## Description

Commits `4e52feba3` and `cac1f165f`. Added the Modelo 390 verification
predicates that compare the annual ledger totals to the reconciliacion-303 folded
totals, first for deducible cuota and then for the devengada / deducible /
resultado trio.

## Outcome

W03.P06.S16 complete. The M390 registry now carries blocking reconciliation
predicates for annual ledger-vs-M303 fold divergence, and the tests cover both
registry declaration and predicate evaluation.

## Notes

Verification on 2026-07-02:
`uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_modelo_390_registry.py src/aeat/application/modelo/tests/test_verification_m390_reconciliation.py`
passed, 23 tests. Full output is in `_scratch-wave1-d9/m390-reconciliation-tests.log`.
