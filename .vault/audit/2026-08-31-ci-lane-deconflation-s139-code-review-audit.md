---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:6dab9d4bbbdf333ca2b3082b4fcb259d2d2355c9a3b7ff75817867dd544ea503'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ci-lane-deconflation` audit: `P05 S139 independent code review`

## Scope

Independent review of P05.S139 at `a464bfa131078a1732037adc83e010e230715a02`, with current HEAD confirmed at that revision. Reviewed the governing CI-lane plan, applicable rules and audit template, the S139 execution record, and all five changed paths. Checked the external-evidence/justificante extraction, call and import ownership, public exports, literal evidence, custody-failure attribution, size/baseline scope, and plan/exec mapping.

## Findings

### s139-code-review | high | The old clean-state module remains a public forwarding facade

`cross_period_clean_state.py` imports `filing_external_evidence_blockers` from `_cross_period_external_evidence.py` at line 51 and continues to list it in `__all__` at line 1126. This preserves the obsolete `cross_period_clean_state.filing_external_evidence_blockers` public route after the extraction, rather than leaving the defining sibling as the sole canonical owner. Remove the old import and `__all__` entry, and move any consumer of that old route directly to the defining sibling.

The extracted predicate and justificante checks otherwise remain behaviorally intact. The package-level import is direct from the defining sibling, ruff and format evidence is complete, and the record declares marker-free collection of 31 tests with zero deselection. The recorded 11 custody failures occur before evidence execution: each affected test enters `isolated_runtime_profile` before persistence and the blocker call, and an independent targeted run of `test_unresolved_identity_is_not_a_mismatch.py` passed all 5 tests in 11.12 seconds. The `KDF_SUPERVISION_UNAVAILABLE`/worker-pipe EOF is therefore external to S139 rather than hidden evidence failure. No policy, baseline, or threshold path changed; recorded 1,128 and 130 lines remain under the 1,250 cap.

## Recommendations

Repair the HIGH by deleting the forwarding export from `cross_period_clean_state.py` and updating any residual consumers to import `filing_external_evidence_blockers` from `_cross_period_external_evidence.py` directly. Re-run the recorded focused collection and behavior suite after the repair.
