---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7f506e5f7929528007fd5e4efe3dd4a79b214600a75ba654cc9b83d0c260e800'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` audit: `P05 S139 independent code review`

## Scope

Independent review of P05.S139 at `a464bfa131078a1732037adc83e010e230715a02`, with current HEAD confirmed at that revision. Reviewed the governing CI-lane plan, applicable rules and audit template, the S139 execution record, and all five changed paths. Checked the external-evidence/justificante extraction, call and import ownership, public exports, literal evidence, custody-failure attribution, size/baseline scope, and plan/exec mapping.

## Findings

### s139-code-review | high | The old clean-state module remains a public forwarding facade

`cross_period_clean_state.py` imports `filing_external_evidence_blockers` from `_cross_period_external_evidence.py` at line 51 and continues to list it in `__all__` at line 1126. This preserves the obsolete `cross_period_clean_state.filing_external_evidence_blockers` public route after the extraction, rather than leaving the defining sibling as the sole canonical owner. Remove the old import and `__all__` entry, and move any consumer of that old route directly to the defining sibling.

The extracted predicate and justificante checks otherwise remain behaviorally intact. The package-level import is direct from the defining sibling, ruff and format evidence is complete, and the record declares marker-free collection of 31 tests with zero deselection. The recorded 11 custody failures occur before evidence execution: each affected test enters `isolated_runtime_profile` before persistence and the blocker call, and an independent targeted run of `test_unresolved_identity_is_not_a_mismatch.py` passed all 5 tests in 11.12 seconds. The `KDF_SUPERVISION_UNAVAILABLE`/worker-pipe EOF is therefore external to S139 rather than hidden evidence failure. No policy, baseline, or threshold path changed; recorded 1,128 and 130 lines remain under the 1,250 cap.

## Recommendations

Repair the HIGH by deleting the forwarding export from `cross_period_clean_state.py` and updating any residual consumers to import `filing_external_evidence_blockers` from `_cross_period_external_evidence.py` directly. Re-run the recorded focused collection and behavior suite after the repair.
