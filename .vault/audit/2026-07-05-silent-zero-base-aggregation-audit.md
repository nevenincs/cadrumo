---
tags:
  - '#audit'
  - '#silent-zero-base-aggregation'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:e0889783949a3501fbd56965d9a1f6fdef10ba555abb6ea4ace5a56d52949c47'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

# `silent-zero-base-aggregation` audit: `campaign close honesty review`

## Scope

Fresh-context campaign-close honesty review for `silent-zero-base-aggregation` after reconciling the two open prorrata volume rows, `W01.P02.S03` and `W01.P02.S04`.

The review treated the campaign as newly inherited: re-read the plan status at HEAD, refreshed semantic vault and code discovery, confirmed the current prorrata implementation with targeted grep, checked the focused prorrata tests, and verified that every plan row now has an exec record or a formal deferral record.

## Findings

### m303-prorrata-volume-deferral-still-valid | medium | per-period volume bindings would be wrong regulated values

The refreshed review confirms the original ADR decision still matches HEAD. `iva.prorrata-volumen-total` and `iva.prorrata-volumen-con-derecho` are annual prorrata inputs whose regulated use depends on the prior-year definitive percentage applied provisionally and a settlement-period regularisation against current-year annual volumes. A current-period `base_amount_sum` binding would only be safe for the fully taxable case, which is already covered by the full-deduction default. For mixed traders it would emit a wrong regulated percentage, so `W01.P02.S03` and `W01.P02.S04` are closed as formal deferrals, not as shipped registry bindings.

### prorrata-follow-up-named | medium | deferral target is the cross-period prorrata mechanism

The deferral has a named follow-up rather than an open-ended gap: the cross-period prorrata regularisation mechanism, including provisional-percentage carry and fourth-quarter or annual settlement regularisation. HEAD already keeps `PRORRATA_REGULARIZACION` as a deferred source kind and surfaces the current advisory path instead of promoting an automatic casilla feed. No new binding source kind, resolver convention, or validator convention is introduced by this closure pass.

### plan-closure-reconciled | low | all silent-zero rows now carry evidence

`vault plan status` reports 18 of 18 steps complete with no missing exec records. `W01.P02.S03` and `W01.P02.S04` now have dedicated exec records documenting their blockers and follow-up, and the plan check is clean. The focused prorrata verification also passed: `pytest -q -n 0` over the prorrata advisory and IVA prorrata tests reported 38 passed.

### close-review-residual | low | no additional silent-zero bounded-mirror work surfaced in this pass

Within the scope of this close review, semantic search, grep confirmation, plan status, and focused prorrata gates did not surface another open silent-zero bounded-mirror obligation. The remaining prorrata work belongs to the separately deferred cross-period prorrata mechanism, not to this campaign's bounded mirror closure.

## Recommendations

- Treat `silent-zero-base-aggregation` as closed with `W01.P02.S03` and `W01.P02.S04` formally deferred.
- Do not add per-period prorrata volume bindings for the mixed-trader case.
- Keep `PRORRATA_REGULARIZACION` deferred until the cross-period prorrata carry and settlement regularisation path is designed, implemented, and verified under its own authority.
- Use the `W01.P02.S03` and `W01.P02.S04` exec records as the closure evidence for this campaign.
