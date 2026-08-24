---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ead4746ea86cc7c8f6e2df0ecd1bd6186d026d2bffc3a0a086f10eba779cd13f'
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

## Outcome

Commit `0e9c4bbb36` establishes structured Pydantic proof-cause assertions for the three named live failures and proves the composer preserves their fail-closed missing-evidence taxonomy. The focused command passed with 50 tests, as independently recorded in the S51 post-review audit.

## Notes

The direct `value_error` fallback mapping is covered, but this step did not make live connected-proof revalidation emit a generic `ValueError` and then prove the composed refusal. The independent S51 review recorded that gap as a medium finding; W01.P02.S54 owns the live fallback and mutation-bite proof. No production data or persistent evidence was altered by the focused tests.
