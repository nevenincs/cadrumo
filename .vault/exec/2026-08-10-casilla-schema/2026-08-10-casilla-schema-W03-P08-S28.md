---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:e58fd91c48497ed70e075d7a87de44e9d1737cd0b428bb3a3b805d9cb36c36e9'
step_id: 'S28'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# S28 pipeline-health persisted-readiness authority

## Scope

- `src/cadrumo/application/overview/_pipeline_health.py`
- `src/cadrumo/entrypoints/cli/tests/test_overview_pipeline_verb.py`
- Exact `cli.overview.pipeline` leaves in the four locale catalogues

## Description

- Make the latest persisted `VerificationReport.completeness_status` and `granted_verificado_completo` authoritative for non-filed pipeline readiness.
- Render persisted `INCOMPLETE` separately from a calculated revision with no verification report, while retaining conclusive filed lifecycle precedence.
- Keep finding severities as display counts only and stop deriving verification readiness from `CalculationRevisionState`.
- Prove parity through the exact CLI with a genuine zero-finding incomplete report in the encrypted repository.
- Localise the new incomplete summary and expanded help through `dev.locales`, using the internal Spanish `INCOMPLETO` stem and preserving the `incomplete` wire value.

## Outcome

Pipeline health now reports `calculated` only when the current revision has no persisted verification outcome, `incomplete` for the latest persisted incomplete outcome, `blocked` for the persisted blocked outcome, and `verified` only for a complete outcome that granted `verificado_completo`. Presented revisions remain filed regardless of a preceding verification report.

Implementation and its real CLI regression landed in `5e91761461`. The initial execution record and review-audit scaffold were absorbed together by concurrent commit `8a1f493506`; the completed audit body and this corrected lifecycle closure are therefore a follow-up only. Shared history is not rewritten.

Focused verification passed:

- exact persisted-report CLI parity regression and typed transport regression: 2 passed;
- Ruff over the changed Python implementation and test: passed;
- strict BasedPyright over the changed Python implementation and test: zero errors, warnings, or notes;
- direct runtime resolution of the new summary and help in all four locales: passed;
- `git diff --check`: passed.

## Notes

The formal review approved S28 with no runtime findings. Its LOW execution-record hygiene finding is resolved by this VaultSpec-CLI-only body replacement, which removes all scaffold comments and extra blank lines. The wider integration module remains red only because its pre-existing shared profile helper omits a newly required profile fact; the S28 regression uses a complete real profile and passes. Locale scaffold and audit remain red only on unrelated catalogue drift and do not name either S28 key. These are explicit broader-tree boundaries, not S28 failures.
