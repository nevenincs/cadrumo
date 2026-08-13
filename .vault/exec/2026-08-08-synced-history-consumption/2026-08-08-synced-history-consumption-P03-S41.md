---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:de59452d3475c08815f7180654488433513b28f70eff9e1709a2ad0e5d4ba762'
step_id: 'S41'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---
# Rerun the fourteen affected isolated sequence goldens and five owning-page coherence gates after the performance and diagnostic proofs pass, preserving CLI-owned goldens.

## Scope

- `docs/_sequences`
- `docs/how-to`
- `dev/docs/sequences`

## Description

- Remove the duplicate `evidence_id` capture, evidence registration, and attachment frames from the `verification-reports-modelo-303` contract because `autonomo-irpf-2026` is the canonical seed owner.
- Regenerate only `verification-reports-modelo-303` through `dev.docs.sequences refresh` after the contract change.
- Run the fourteen S18 isolated sequence checks through the public `check --sequence` command with the bounded 180-second timeout.
- Run the five owning pages through the public `check --page --coherence` command with the same bound.

## Outcome

The repaired `verification-reports-modelo-303` sequence passed in isolation in 43.7 seconds and its owning-page coherence gate passed in 54.0 seconds. Its generated JSON golden was refreshed only by the canonical CLI.

All fourteen affected isolated goldens passed: `first-quarter-export-file`, `modelo-130-first-quarter`, `irpf-lifecycle-q1`, `irpf-lifecycle-q2`, `modelo-130-export-file`, `modelo-130-inspect-boxes`, `modelo-130-manual-casilla`, `modelo-130-quarterly`, `modelo-130-review-chain`, `quickstart-modelo-130`, `quickstart-revision`, `review-values-bindings`, `review-values-manual-casilla`, and `review-values-review-saved`.

All five cumulative owning-page gates passed within the public bound: `how-to/first-quarterly-filing` in 30.7 seconds, `how-to/irpf-lifecycle` in 68.3 seconds, `how-to/modelo-130` in 60.0 seconds, `how-to/quickstart` in 39.9 seconds, and `how-to/review-calculation-values` in 32.0 seconds.

## Notes

The runner's `runpy` module warning was emitted after successful checks and did not produce a timeout receipt or a golden or coherence divergence. No golden JSON was edited by hand.
