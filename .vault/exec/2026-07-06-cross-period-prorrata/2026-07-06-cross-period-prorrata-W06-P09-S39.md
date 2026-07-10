---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-08'
step_id: 'S39'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# record the deferred automatic art-104.Tres exclusion classification in the ledger rollup as a follow-up (the rollup stays a reconciliation check until it lands)

## Scope

- `.vault/exec/2026-07-06-cross-period-prorrata/`

## Description

- Re-read the live plan status and confirmed `W06.P09.S39` was the next open step after S38.
- Re-grounded the follow-up through semantic vault and code search against the cross-period prorrata ADR, the W06 plan row, the current ledger-volume divergence helper, and the domain IVA prorrata input contract.
- Confirmed `ProrrataInputs` requires callers to supply annual operation totals with art. 104 exclusions already applied, including subvenciones not linked to operations, autoconsumos, bienes de inversion disposals, and non-recurring financial or immovable operations meeting the art. 104.Tres tests.
- Confirmed the current declared-volume ledger rollup is deliberately advisory-only: it windows existing IVA ledger observations with `Period.contains`, classifies visible output volume into con-derecho/sin-derecho buckets, and warns on divergence while preserving declared casilla authority.
- Recorded the remaining automatic-classification gap honestly: the rollup cannot become authoritative until ledger evidence carries enough facts to identify every art. 104.Tres exclusion without guessing.

## Outcome

- S39 is formally deferred.
- The current ledger rollup remains a reconciliation check, not an automatic source of filed annual prorrata volumes.
- Follow-up: add grounded ledger classification for the art. 104.Tres exclusion set, prove excluded operations are removed from both numerator and denominator, then reconsider whether the rollup can feed anything beyond a divergence advisory.
- No source kind, resolver convention, validator convention, or registry selector was added.

## Notes

- Verification passed: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_prorrata_regularizacion.py src\aeat\domain\iva\tests\test_prorrata.py -n 0`.
- Verification passed: `uv run --no-sync vaultspec-core vault check features --feature cross-period-prorrata`.
