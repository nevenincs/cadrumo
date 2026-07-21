---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Filter the art-104.Tres exclusions from the annual volume rollup and keep it a reconciliation pre-fill proposal, never a silent filed-volume authority

## Scope

- `src/aeat/application/aggregation/_iva_ledger.py`
- `src/aeat/application/calculations/_prorrata_regularizacion.py`

## Description

- Collect operator-tagged art-104.Tres judgment operations during IVA ledger aggregation into a new `IvaLedgerAggregation.art_104_tres_excluded_ledger_ids` tuple; the tagged operation still projects its own IVA cuota observation (it is a real taxable supply) - only its ledger id is recorded.
- Add an `art_104_tres_excluded_ledger_ids` parameter to `build_prorrata_declared_volume_divergence_advisory` that skips those ledger ids from BOTH terms of the art-104.Dos ratio when summing the ledger volumes, and records them on `ProrrataDeclaredVolumeLedgerRollup.art_104_tres_excluded_ledger_ids`.
- Extend the divergence advisory message to name the applied art-104.Tres exclusion count so the exclusion is visible, never a silent denominator change.
- Add behaviour tests: aggregation collects the tagged ledger id; the rollup removes it from both terms and records it; the divergence message surfaces it.

## Outcome

- Modified files: `src/aeat/application/aggregation/_iva_ledger.py`, `src/aeat/application/aggregation/tests/test_iva_ledger.py`, `src/aeat/application/calculations/_prorrata_regularizacion.py`, `src/aeat/application/calculations/tests/test_prorrata_regularizacion.py`.
- 47 focused iva-ledger + prorrata-regularizacion tests pass; ruff / ruff-format / ty clean.
- The rollup remains a reconciliation pre-fill proposal: the operator-declared annual volume casillas keep the filing authority and the divergence still surfaces.
- Committed as `10b8ac4ddb`.

## Notes

- To keep the change within the declared file scope, the exclusion is threaded via `IvaLedgerAggregation` plus the builder parameter rather than adding a field to the `IvaLedgerObservation` carrier in the registry package.
- The divergence advisory has no live production caller yet (it is advisory infrastructure the parent cross-period-prorrata ADR shipped), so the exclusion mechanism is proven by the S05 oracle and the S03 behaviour tests; its wiring into a live calculate path is the ADR-D2 promotion, deferred.
- Grounding reconciliation with the art-104.Tres ADR decision D1: the ADR states the IVA taxonomy "already carries the autoconsumo categories", but `IvaCategory` has NO explicit autoconsumo member. This does not weaken the mechanism. Of the six exclusions, only the two judgment exclusions (foreign permanent establishment, non-habitual inmobiliario/financiero) need the new operator tag. The other four are excluded WITHOUT new code: (2) direct cuotas are structural (the volume rollup sums bases/contraprestaciones, never cuotas); (5) art-7 no-sujetas resolve through `IvaCategory.OPERACION_NO_SUJETA`, which `_prorrata_volume_side` already maps to neither ratio term; (6) art-9.1.d autoconsumos and every other non-con-derecho category likewise return None from `_prorrata_volume_side`, so they never enter either term. (3) bienes-de-inversion disposal stays a deferred cross-campaign read of the bienes-inversion register (read-only, not implemented in W01). No exclusion figure is fabricated; the auto-derived cases are excluded by the pre-existing volume-side classification, not invented.
