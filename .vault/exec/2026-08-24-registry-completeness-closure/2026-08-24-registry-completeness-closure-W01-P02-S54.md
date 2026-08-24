---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:314eab93596af0cf624ef86853d8a2c77b052a2209cd0ea0fa7a5f111162fdae'
step_id: 'S54'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Drive a generic ValueError through live connected-proof revalidation and prove the closure composer maps the fallback cause to a fail-closed missing-evidence refusal with a mutation bite.

## Scope

- `src/cadrumo/application/registry/tests/`
- `src/cadrumo/core/tests/`

## Description

- Add an integration regression that starts with a real encrypted, connected census proof admitted by `LiveSourceConnectivityProofAuthority`.
- Corrupt the admitted in-memory row before report composition so the live revalidation returns Pydantic's generic `value_error` for a missing connected proof.
- Assert that the error type maps to `LIVE_PROOF_VALIDATION_FAILED` and that `compose_source_connectivity_coverage` returns an actionable `refused` source limb with the `missing_evidence` reason.
- Deliberately classify the fallback as a digest mismatch, run the new regression to prove it fails, then restore the exact production condition.

## Outcome

The closure composer now has report-boundary coverage for the generic live-proof validation fallback. A malformed row is not trusted because it was previously admitted: revalidation produces `value_error`, the typed cause becomes `LIVE_PROOF_VALIDATION_FAILED`, and the report refuses the affected revision as missing evidence. The focused integration regression passed: 1 passed, 21 deselected in 27.08s. Ruff and the targeted whitespace check passed.

## Notes

The mutation bite temporarily added `LIVE_PROOF_VALIDATION_FAILED` to the digest-conflict branch. The focused regression then failed exactly as expected because the refusal changed from `missing_evidence` to `conflicting_evidence`; the original one-cause condition was restored and verified with an empty production diff. A duplicate restored test run was stopped during shared integration startup after the already-passing clean run, so no source, persisted evidence, or peer work remained modified.
