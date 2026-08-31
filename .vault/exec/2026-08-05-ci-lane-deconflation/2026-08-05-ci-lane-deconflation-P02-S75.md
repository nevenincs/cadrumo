---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:b323239f871bacb61aa145f7359482fa1a91806740f9f5416d1f5a4cb4efe4cb'
step_id: 'S75'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Implement the Modelo 390 regimen simplificado applicability ruling by Route B, and close the seventh and last red M390 test. VERIFIED: test_verify_modelo_revision_refuses_m390_when_prior_filings_are_not_clean now reaches its INTENDED unclean-priors refusal instead of the aggregation-binding one, and all 27 calculation-route tests pass. Built exactly as the corrected shape required -- applicability is SUPPLIED, never reached for across a package boundary. m303_regimen_simplificado_annual_summary_applies now lives in application/modelo/_m303_regimen_simplificado_scope.py beside the other scope derivations, which is its natural home and also avoids an import cycle; it delegates to the closed vocabulary rather than reading the profile, so GENERAL maps to not-claimed, SIMPLIFIED and MIXED to evidence-required, and an unknown composition still refuses instead of defaulting. FOUR SITES, ONE DERIVATION: the resolver takes regimen_simplificado_applies and returns an empty resolution when the regime does not reach the filer; the guard's antecedent widened from 'declares' to 'declares AND applies', carrying expects_handoff into its diagnostic context beside declares_handoff so a refusal says which half failed; validate_persisted_target_revision treats inapplicable exactly as undeclared, since neither can produce a handoff, so an absent one is correct and a persisted one equally anomalous; and _verification_actions passes the same derivation. The arrival-path invariant is intact -- a missing or unexpected handoff is still refused wherever the regime DOES reach the taxpayer. UNBLOCKED A PRIORITY-1 BREAKAGE FOUND WHILE VERIFYING, and it was mine: the design_constant BindingSourceKind admitted earlier in this campaign never declared an OperatorActionAxis, and _assert_total_action_projection is a TOTAL import-time assertion over every member. That raised at import and left 14 application test modules uncollectable -- the failure was invisible until a module outside the -k 390 filter was collected. Fixed by declaring REVIEW_ADVISORY, the only honest axis: a diseno-fixed constant can never await operator data entry, so an unready one is a registry defect to review rather than a task, and its readiness key cli.app.modelo.bindings.readiness.constante_diseno was authored in all FOUR catalogues through the dev.locales CLI as the parity gate and honesty ratchet require. Collection went from 14 errors to zero. TWO ROUTE GATES CORRECTED, NOT WEAKENED: both pinned the manual-stage inventory POSITIONALLY, one via OWNERSHIP[-1] and one via OWNERSHIP[:-1], written when the manual stage held a single row. The design-constant sibling made both silently test the wrong row -- the second so badly that its refusal was never reached, since slicing dropped the sibling and left a duplicate id that raised a different error first. Both now select the manual-input owner BY TYPE, the manual stage pins BOTH pseudo-owners so a third cannot appear unnoticed, and the single-instance invariant still bites because the production check keys on isinstance rather than on stage or position. NOT MINE, FLAGGED NOT CLAIMED: test_cross_period_clean_state_blocks_csv_register_without_justificante_verification and its accepts_ sibling fail on MISSING_EXTERNAL_EVIDENCE_RECORD where they expect MISMATCHED_. Nothing in this change touches the cross-period evaluation path, the module has no recent commit, and this shared worktree currently carries uncommitted peer edits under adapters/persistence/storage. Investigate separately rather than absorbing into this fix

## Scope

- `src/cadrumo/application/modelo/_m303_regimen_simplificado_scope.py`
- `src/cadrumo/application/modelo/_calculation_actions.py`
- `src/cadrumo/application/modelo/_verification_actions.py`
- `src/cadrumo/application/calculations/_m303_regimen_simplificado_annual_summary.py`
- `src/cadrumo/application/state_projection.py`
- `src/cadrumo/application/modelo/tests/test_calculation_route.py`

## Changes

- `M` `src/cadrumo/application/calculations/_m303_regimen_simplificado_annual_summary.py`
- `M` `src/cadrumo/application/modelo/_calculation_actions.py`
- `M` `src/cadrumo/application/modelo/_m303_regimen_simplificado_scope.py`
- `M` `src/cadrumo/application/modelo/_verification_actions.py`
- `M` `src/cadrumo/application/modelo/tests/test_calculation_route.py`
- `M` `src/cadrumo/application/state_projection.py`

## Notes

- Source provenance is `94187f454c55ddd1df6265d7f66601c0df4fdfe2`. That commit co-lands storage and operations work, so this manifest identifies only the relevant S75 hunks and does not attribute its peer paths to this Step.
- Route B is implemented by retaining `m303_regimen_simplificado_annual_summary_applies` in `application/modelo`, supplying its boolean to the calculations resolver, returning an empty resolution for a non-applicable taxpayer, and using the same derivation for the calculate, verification, and persisted-target boundaries. The declared-and-applicable guard leaves the one mesh-owned arrival-path refusal intact when the regime applies.
- The plan's statement that the target unclean-priors refusal is reached and 27 calculation-route tests pass is historical plan prose. No literal command or stdout receipt is recoverable, so it is not represented as a verification receipt here.
- S75 does not borrow S74's design-correction evidence. Current annual-summary resolver and calculation-actions files are `MM` in shared WIP; no fresh pytest run was attempted. The separately flagged cross-period clean-state failure remains outside this Step.
