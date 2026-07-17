---
tags:
  - '#audit'
  - '#binding-resolver-contract-unification'
date: '2026-07-05'
modified: '2026-07-17'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

# `binding-resolver-contract-unification` audit: `campaign close honesty review`

## Scope

Fresh-context campaign-close honesty review for `binding-resolver-contract-unification` after reconciling the remaining open rows `P03.S21`, `P03.S20`, `P03.S12`, and `P05.S18`.

The review re-read the authoritative plan status at HEAD, the resolver-contract ADR execution refinement, the counterpart-source provider ADR, the existing blocker exec records, the current source-mesh disposition, and the current focused counterpart and foreign-assets test slices. It then checked the remaining plan rows only as formal deferrals against existing exec evidence, not as implementation completions.

## Findings

### counterpart-follow-up-formally-deferred | medium | S21 is not a completed 347/349 mesh-equality proof

The current counterpart test slice passes, but it does not satisfy the original `P03.S21` wording. The accepted counterpart-source provider ADR changes the honest closure shape: invoice-owned counterpart sources remain owned by the invoice resolver, the counterpart aggregate resolver must not claim them, and a future repository-backed provider is condition-triggered on a declaring registry binding. `P03.S21` is therefore closed as a formal deferral to that provider/enrollment follow-up, not as a claim that the live mesh now equals `aggregate_counterpart_347` and `aggregate_counterpart_349` for both fixtures.

### foreign-assets-row-carrier-still-blocks-live-resolution | medium | S20 remains a row-indexed envelope follow-up

The current M720 focused slice passes, including the row-projection checks, but the resolver still does not expose row-indexed binding values through the scalar `CalculationSourceResolution.binding_values` channel. That matches the existing `P03.S20` blocker record: completing the original live-mesh equality gate requires a coordinator-approved row carrier strategy before `FOREIGN_ASSET` can move out of deferred status. `P03.S20` is closed as a formal deferral, not as a live resolver promotion.

### enrollment-and-final-gate-deferred | medium | S12 and S18 remain downstream of the shape-C follow-ups

`P03.S12` would enroll counterpart and foreign-assets resolvers and remove `FOREIGN_ASSET` from deferred status. That now contradicts the current authority: counterpart remains condition-triggered and M720 remains blocked on the row carrier. `P05.S18` is likewise downstream of those P03 decisions, so the full resolver-contract final gate was not claimed. Both rows are checked only because their exec records name the blockers and follow-ups.

### plan-evidence-reconciled | low | plan rows and exec evidence now align

`vault plan status` now reports 21 of 21 steps complete with no missing exec records. The only plan-check finding is `PLAN022`, the known non-monotonic row-order warning introduced by the inserted `S21` and `S20` rows; it is not an evidence or closure defect. No new source kind, resolver convention, or validator convention was introduced by this reconciliation.

### scoped-verification-current | low | current focused slices pass but do not erase the deferrals

The current sequential focused checks passed: the counterpart slice reported 3 passed and 22 deselected, and the foreign-assets slice reported 3 passed and 22 deselected. These runs confirm the current follow-up surface is healthy enough to record the formal deferrals, but they are not substitutes for the deferred full live-mesh equality and final-gate work.

## Recommendations

- Treat `binding-resolver-contract-unification` as closed with `P03.S21`, `P03.S20`, `P03.S12`, and `P05.S18` formally deferred.
- Do not enroll the counterpart or foreign-assets resolvers through `merge_source_resolutions` under this plan.
- Keep `FOREIGN_ASSET` deferred until the M720 row carrier strategy is approved and verified.
- Keep counterpart ledger and purchase-evidence kinds reserved until a declaring registry binding and the repository-backed provider enrollment co-land.
- Run the full resolver-contract final gate only after those follow-ups land under their own authority.
