---
tags:
  - '#exec'
  - '#adr-amendment-implementing-rows'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:b38f77f4a327961372f081420d38ab0756d1c6b9ef6dce261e4a65f70b507b96'
step_id: 'S04'
related:
  - "[[2026-08-07-adr-amendment-implementing-rows-plan]]"
---
# Land the recargo mismatch advisory comparing an operator-supplied recargo figure against the rate resolved for its applied rate and date

## Scope

- `src/cadrumo/application/aggregation/`

## Description

- Reconcile the accepted source-of-truth ADR with current HEAD and commit `83b78ac464`.
- Confirm the advisory compares the recorded recargo without mutating the declared figure.
- Confirm a missing rate-table pairing remains silent and that a divergent pairing emits a typed non-blocking diagnostic.
- Run the focused real-behavior test and an external isolated comparison-flip control.

## Outcome

Current HEAD implements S04 in pre-existing commit `83b78ac464`. The recorded invoice amount remains authoritative; a divergent published pairing is an advisory only, and an unmodelled table window produces no mismatch advisory.

## Verification

`uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_recargo_rate_advisory.py -n 0 -q`

`7 passed in 5.26s`

The external isolated source copy reversed the matching comparison from `==` to `!=` and ran the matching-rate control:

`1 failed, 6 deselected in 45.81s`

The failure was `test_a_recargo_matching_the_published_rate_raises_nothing`, proving the control detects that comparison flip.

## Notes

No production file changed in this reconciliation. The environment blocked removal of the disposable external mutation copy after the proof; it contains only copied source and is outside this repository.
