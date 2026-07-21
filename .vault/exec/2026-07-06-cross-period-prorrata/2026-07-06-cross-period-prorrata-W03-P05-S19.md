---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S19'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# thread the register's active-general provisional percentage into the shared LedgerIvaAggregationSourceResolver deducible-cuota path so it apportions the deducible cuotas (art-104.Uno + 105.Uno), leaving bases unapportioned

## Scope

- `src/aeat/application/aggregation/_iva_ledger.py`

## Description

- Ground discovery with semantic search for prorrata provisional ledger IVA
  deducible cuota apportionment, then confirm the current implementation with
  targeted grep and full reads of `src/aeat/application/aggregation/_iva_ledger.py`,
  `src/aeat/application/aggregation/_modelo_bindings.py`, and the accepted
  cross-period prorrata ADR.
- Add an internal `IvaLedgerProrrataApportionment` carrier to the IVA ledger
  aggregation result, resolved from the encrypted prorrata register for the
  filing year only when the whole-entity entry is active `general` and the
  declared domain precedence ladder resolves a provisional percentage.
- Add `resolve_iva_ledger_binding_values` as the shared application-layer IVA
  binding resolver wrapper: it delegates to the existing registry
  `ledger_iva_aggregation` selector resolver, then applies the prorrata
  percentage only to revision casilla bindings in a `deducible` section whose
  selector fact is `iva_amount_sum`.
- Switch `LedgerIvaAggregationSourceResolver` and its M303 invoice-evidence
  guard to use the application wrapper so reverse-charge devengado cuotas and
  base bindings stay unapportioned while soportado/import/reverse-charge
  deducible cuota bindings are reduced.
- Record the required S19 implementation review in the feature audit with no
  open implementation findings.

## Outcome

- The shared IVA ledger source resolver now threads the active general prorrata
  provisional percentage into the deducible-cuota binding path without changing
  the source kind, binding selector taxonomy, or validator convention.
- Non-prorrata taxpayers remain byte-identical by construction: absent register
  entry, non-`general` regime, unresolved percentage, and a `100` percent
  prorrata all pass through the original binding values.
- Bases remain unapportioned because the postprocess excludes `base_amount_sum`
  bindings even when the target casilla sits in a deducible section.

## Notes

- Verification passed: `uv run --no-sync ruff check src\aeat\application\aggregation\_iva_ledger.py src\aeat\application\aggregation\_modelo_bindings.py`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\aggregation\tests\test_iva_ledger.py -k "not preclassified and not projected" -n 0` (26 passed, 7 deselected).
- Broader registry-backed IVA regression commands failed before reaching the
  S19 path on unrelated Modelo 714 registry validation diagnostics (missing
  source citations, construct legal/source ref coverage, and source revision
  coverage). The failure reproduced sequentially with `-n 0`, so it is not a
  parallel loader-cache race.
