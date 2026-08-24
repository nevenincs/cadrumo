---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0a2df534a10e4b3668517bb39e9b02d035f9c83f89c1d7a7b875b568056369f4'
step_id: 'S51'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Assert structured Pydantic proof-cause codes and composer taxonomy for source-enrollment, operator-workflow, and encrypted-provenance failures, with a ValueError-fallback mutation bite.

## Scope

- `src/cadrumo/core/tests/`
- `src/cadrumo/application/registry/tests/`

## Description

- Assert that source-enrollment, operator-workflow, and encrypted-provenance failures emit their stable `SourceConnectivityProofFailureCause` Pydantic error types at the live validation boundary.
- Pass each classified live-proof failure through `compose_source_connectivity_coverage` and assert its refused limb reports `missing_evidence`; retain the existing digest-mismatch path as `conflicting_evidence`.
- Assert that Pydantic's generic `value_error` type resolves to the closed `LIVE_PROOF_VALIDATION_FAILED` fallback cause while the three classified failures do not collapse to that fallback.
- Run the focused core and registry source-connectivity test modules.
- Re-attest the checked Step after S54's independent review: its live generic-`ValueError` revalidation regression and deliberate refusal-taxonomy mutation bite supply the report-boundary proof that did not exist when this record was first completed.

## Outcome

Commit `0e9c4bbb36` establishes structured Pydantic proof-cause assertions for the three named live failures and proves the composer preserves their fail-closed missing-evidence taxonomy. The focused command passed with 50 tests, as independently recorded in the S51 post-review audit. Commit `d125ec60abd` then drives the generic validation failure through live connected-proof revalidation, proves the report refuses it as missing evidence, and includes the deliberate taxonomy mutation bite. Its independent post-review at `9ca4c7883e` passes. Together, the separately preserved S51 and S54 evidence satisfy the complete S51 acceptance statement.

## Notes

At the original S51 landing, only the direct `value_error` fallback mapping was covered; the independent S51 review recorded the absent live report-boundary proof and S54 owned it. The S55 post-review correctly raised a high tracking finding because S51 remained checked while that later proof was open. S56 reconciles this record to the independently reviewed S54 evidence without rebasing, reattributing, or otherwise rewriting either implementation commit. No production data or persistent evidence was altered by the focused tests.
