---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:06deeed4deb741c1f0a65799296b720d9189b451432e3f51055af9244c5aef52'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
  - "[[2026-08-24-registry-completeness-closure-adr]]"
---

# `registry-completeness-closure` audit: `S49 structured proof cause review`

## Scope

Independent post-implementation review of commit `9a1f88e83d` against the accepted
closure decision and `W01.P02.S49`. The review covered the core proof-cause home and
facade, Pydantic error-code propagation, the missing-versus-digest-drift mapping,
the absence of prose parsing, and the live encrypted-repository composer regressions.

The implementation correctly keeps the closed cause in the core proof contract,
exports it through the core facade, and maps only
`executable_evidence_digest_mismatch` to `conflicting_evidence`. It uses the
Pydantic error type rather than rendered detail, and the selected Ruff and pytest lane
passed: 54 passed, 18 integration-marked tests deselected.

## Findings

### pydantic-cause-contract | medium | Three advertised stable error types have no exact-code regression

`SourceConnectivityCensusRow._verify_connected_authority` now emits closed
Pydantic error types for source enrollment, operator workflow, and encrypted
provenance mismatch, but the focused core and live-authority tests still assert only
their rendered messages. Only the missing-evidence and digest-mismatch cases assert
`ValidationError.errors()[0]["type"]` and pass it through the cause mapper. A future
regression from `PydanticCustomError` back to `ValueError` on any of the other three
paths would retain the same prose, fall back to
`source_connectivity_live_proof_validation_failed`, and remain invisible to the
current suite. This leaves the claimed stable Pydantic cause contract only partially
proven.

## Recommendations

- Add parameterized core or live-authority regressions for source-not-enrolled,
  operator-workflow-unsupported, and encrypted-provenance-mismatch. Assert each exact
  Pydantic error type and its `SourceConnectivityProofFailureCause` mapping, then
  rerun the selected S49 lane.
