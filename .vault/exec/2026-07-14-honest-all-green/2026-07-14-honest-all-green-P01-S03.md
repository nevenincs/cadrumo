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

11 of the ~12 cascade findings are now GREEN. One category remains OPEN and
is NOT this step's to close unilaterally:

1. RESOLVED (follow-up by another executor holding the S01 diagnosis
   context): `test_taxation_comparison.py`'s in-flight peer WIP completed —
   the `0501` computed-input removal is paired with a
   `renta-2025-profile-has-economic-activity` supply in both the shared
   `_BASE_BINDINGS` fixture and the `test_verify.py` grounded-fraction test
   (the same under-supply class S02 fixed for the registry-level tests).
   All 9 tests in the file pass; the assertions still check the real
   recommendation direction / delta sign / typed envelope contract per the
   module's own no-tautological-test docstring, not vacuously. Commit
   `c76e9639b5`.
2. STILL OPEN: `test_file_flow_filing.py::test_file_runs_workflow_gate_and_refuses_before_state_writes_when_preflight_blocks`
   and `test_file_flow_verify.py::test_verify_runs_workflow_gate_and_refuses_before_verified_state_write`
   assert the OBSOLETE premise that an unavailable auth provider blocks the
   LOCAL file/verify flow. Commit `93bd51b0ab` ("fix(modelo): auth readiness
   gates only live purposes per operator ruling") deliberately narrowed
   preflight gate-4 to skip the local build/verify/file/export flow, so an
   unavailable auth provider no longer blocks. Independently re-confirmed
   this finding by reading `application/workflow/_engine.py`'s
   `skip_auth = purpose in (WorkflowPurpose.VERIFY, WorkflowPurpose.FILE)`
   and the test harness's `_workflow_gate` helper
   (`application/modelo/tests/_file_flow_support.py`): the harness
   constructs its `WorkflowEngine` with `certificate_bundle=None`, so the
   ONE other cert-expiry check that also gates on provider availability is
   structurally inert in this test file too — the `auth_provider` fixture
   these two tests pass has no reachable effect on either test's outcome.
   Of the four `SubmissionEngine` preflight gates, only gate-1
   (draft-approval status) and gate-2 (error-severity findings) remain
   un-skipped for FILE/VERIFY; the harness's `_RevisionDraftBuilder`
   unconditionally approves the draft it builds (gate-1 always passes by
   construction), so a genuine replacement blocking condition would need to
   engineer an intentionally-invalid casilla input that trips gate-2 — a
   registry-validation-rule change with real risk of an artificial,
   not-truly-representative fixture if done without deeper domain grounding.
   The "gate refuses -> no partial state written" atomicity invariant these
   tests protect is already covered by the passing
   `test_file_refuses_future_period_before_filing_window_opens` (the
   still-applicable deadline/obligation gate). Reported to the coordinator
   for adjudication rather than guessed a gate-2 fixture.

Commits: `843518562a` (binding count + invoice_repository), `d9fad8f0b7`
(cross-period ca locale rewording), `c76e9639b5` (taxation-comparison
profile-binding supply, closing item 1).

## Notes

- S03 is left OPEN pending item 2 above, a cross-campaign surface (another
  campaign's committed operator ruling) that would either mis-test the
  ruling or fabricate an unrepresentative fixture if closed unilaterally.
  No destructive git; explicit-pathspec commits throughout.
