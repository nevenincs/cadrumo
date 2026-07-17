---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

# Enroll the counterpart and foreign-assets resolvers in merge_source_resolutions and remove FOREIGN_ASSET from DEFERRED_SOURCE_KINDS now that it has a live resolver, applying the apply-cached-on-collision drive against the live peer WIP

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Re-read the current resolver-contract plan status and source-kind deferrals authority before editing the hub file.
- Run semantic discovery for the enrollment target and confirm with source search that `foreign_asset` remains in the structured deferred source-kind declaration.
- Compare the S12 row against the accepted source-kind deferrals ADR, which re-ratifies `foreign_asset` as deferred with no promotion date and requires a grounded design ADR before promotion.
- Reconfirm the existing D9 close-blocker audit: S20 and S21 remain blocked by the M720 row-indexed envelope and M347 counterpart-source modelling, so S12 remains ordered behind incomplete gates.
- Make no `_calculation_actions.py` or source-mesh edit because the requested enrollment now contradicts the governing deferral decision.

## Outcome

- S12 is formally blocked, not implemented.
- `ForeignAssetsAggregationSourceResolver` exists and has test evidence, but the live `CalculationSourceResolution` envelope still has no row-indexed binding-value channel for M720 detail rows. Enrolling it as a scalar mesh resolver would overclaim S20.
- `CounterpartAggregationSourceResolver` has M349 evidence, but Modelo 347 still lacks counterpart-source registry bindings under the current revision. Enrolling it for S21 would overclaim the 347 half.
- Removing `FOREIGN_ASSET` from `DEFERRED_SOURCE_KINDS` would now violate the accepted source-kind deferrals ADR, which explicitly re-ratifies `foreign_asset` with no promotion date and a per-M720 hardening or operator-need review trigger.
- No plan step check was run because this is a blocker record and the plan file still carries non-authored WIP.

## Notes

- Formal blockers: `DFR-D9-P03-S20-M720-ROW-INDEXED-ENVELOPE`, `DFR-D9-P03-S21-M347-COUNTERPART-SOURCE-MODELLING`, and `DFR-D9-P03-S12-SOURCE-KIND-DEFERRAL-CONFLICT`.
- Named follow-up: coordinator-approved M720 row carrier strategy, M347 counterpart-source registry modelling or activation-contract change, then a new authority decision that promotes `foreign_asset` out of deferral before any S12-style mesh enrollment.
