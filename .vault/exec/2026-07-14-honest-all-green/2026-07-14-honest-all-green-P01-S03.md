---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S03'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace honest-all-green with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-14-honest-all-green-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Verify the application/modelo cascade failures clear downstream and fix any residual independent defects and ## Scope

- `src/cadrumo/application/modelo/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify the application/modelo cascade failures clear downstream and fix any residual independent defects

## Scope

- `src/cadrumo/application/modelo/tests`

## Description

- Re-ran the S29 application/modelo cascade at HEAD after the S02 registry
  fixes. Of the ~12 triaged failures, the S02 registry work cleared the
  namesake `application/verification/tests/test_verify.py` grounded-fraction
  test and every registry-downstream calc test.
- Fixed `test_binding_count_is_exactly_38` -> `_39`: the M100 2025 registry
  gained the scalar profile binding `renta-2025-profile-has-economic-activity`;
  bumped the structural-sentinel count and breakdown.
- Fixed `test_actions` and `test_objective_estimation_exclusion_advisory`:
  passed the now-required `invoice_repository=None` kwarg to the private
  `_collect_revision_verification_findings` helper (valid no-repository state).
- Fixed `test_cross_period_clean_state_gates`: the cross-period unclean-notice
  and operator-declared-suppression advisory were reworded in the ca locale
  (unclean clause canonically lowercase per the lowercase English template;
  suppression advisory now explains "exclosa perquè no hi ha obligació prèvia").
  Updated the test's expected Catalan substrings to stable slices of the
  current locale strings.
- Ran the full cascade file set sequentially: 106 passed, only the 2 gate-4
  file-flow tests remain red.

## Outcome

10 of the ~12 cascade findings are GREEN. Two categories remain OPEN and are
NOT this step's to close unilaterally:

1. `test_taxation_comparison.py` (5 tests) carries ACTIVE uncommitted peer WIP
   (a peer removed the now-computed `0501` input but has not yet supplied the
   `renta-2025-profile-has-economic-activity` binding, leaving the file mid-fix
   with the exact profile-binding under-supply S02 fixed elsewhere). Per the
   STOP-on-active-peer-WIP discipline I did not edit it; the peer's in-flight
   fix will complete it. Flagged to the coordinator.
2. `test_file_flow_filing.py::test_file_runs_workflow_gate_and_refuses_before_state_writes_when_preflight_blocks`
   and `test_file_flow_verify.py::test_verify_runs_workflow_gate_and_refuses_before_verified_state_write`
   assert the OBSOLETE premise that an unavailable auth provider blocks the
   LOCAL file/verify flow. Commit `93bd51b0ab` ("fix(modelo): auth readiness
   gates only live purposes per operator ruling") deliberately narrowed
   preflight gate-4 to skip the local build/verify/file/export flow, so an
   unavailable auth provider no longer blocks. The "gate refuses -> no partial
   state written" atomicity invariant these tests protect is already covered by
   the passing `test_file_refuses_future_period_before_filing_window_opens`
   (the still-applicable deadline/obligation gate). Correct resolution is a
   design decision on that campaign's ruling: either invert the two tests to
   assert the local flow now PROCEEDS with an unavailable auth provider
   (locking the ruling), or rework them onto a still-applicable preflight gate.
   Reported to the coordinator for adjudication rather than guessed.

Commits: `843518562a` (binding count + invoice_repository), `d9fad8f0b7`
(cross-period ca locale rewording).

## Notes

- S03 is left OPEN pending the two items above; both are cross-campaign
  surfaces (active peer WIP; another campaign's committed operator ruling), so
  closing them unilaterally would either collide with live work or mis-test an
  operator ruling. No destructive git; explicit-pathspec commits throughout.
