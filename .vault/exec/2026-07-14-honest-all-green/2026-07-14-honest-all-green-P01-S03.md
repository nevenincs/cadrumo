---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-17'
body_hash: 'sha256:b222c388ac3c505639dbc5f2a056fb16b50cc9d1937f479c0743cb78e48c0975'
step_id: 'S03'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

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

ALL ~12 cascade findings are now GREEN; S03 is complete.

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
2. RESOLVED per coordinator adjudication (INVERT to lock the ruling):
   `test_file_flow_filing.py` and `test_file_flow_verify.py`'s two gate
   tests asserted the OBSOLETE premise that an unavailable auth provider
   blocks the LOCAL file/verify flow. Commit `93bd51b0ab` ("fix(modelo):
   auth readiness gates only live purposes per operator ruling") deliberately
   narrowed preflight gate-4 to skip the local build/verify/file/export flow.
   Inverted both to lock the ruling in as regression coverage: renamed to
   `test_file_proceeds_locally_when_auth_provider_unavailable` /
   `test_verify_proceeds_locally_when_auth_provider_unavailable`, asserting the
   local flow now PROCEEDS with an unavailable provider (filing VIGENTE +
   revision PRESENTADO + MODELO_FILED event; verify -> VERIFICADO_COMPLETO +
   report + MODELO_VERIFICATION_PASSED event) and never consults the provider
   (`describe_calls == 0`). Did NOT engineer a synthetic gate-2 fixture (the
   unrepresentative-fixture risk the coordinator concurred with; atomicity is
   already covered by `test_file_refuses_future_period_before_filing_window_opens`,
   the deadline gate). The live-purpose half of the ruling — a non-skipped
   preflight gate-4 STILL refusing on an unavailable provider — was verified
   already pinned by `test_preflight.py::test_gate_4_unavailable_provider_surfaces_structured_context`
   (a genuinely reachable gate-4 refusal, not the inert cert path), so no new
   live-purpose test was needed. Commit `50f272a6a3`.

Commits: `843518562a` (binding count + invoice_repository), `d9fad8f0b7`
(cross-period ca locale rewording), `c76e9639b5` (taxation-comparison
profile-binding supply, closing item 1), `50f272a6a3` (file/verify auth-gate
inversion, closing item 2).

## Notes

- Both open items resolved: item 1 by the stood-down executor, item 2 by the
  coordinator's INVERT adjudication. Both halves of the auth-readiness ruling
  are now pinned as regression coverage (local flow proceeds; live gate-4 still
  refuses). No destructive git; explicit-pathspec commits throughout.
