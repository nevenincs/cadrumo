---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:e5af2dcb242fc29fda1f12dad1dabaa5b1490f2ed0200b731b5c71a8a8ed2ad0'
related:
  - "[[2026-08-05-ci-lane-deconflation-P05-S185]]"
---

# `ci-lane-deconflation` audit: `P05 S185 execution self review`

## Scope

Self-review of the P05.S185 execution record against source provenance `adbdcc8875b9323b3ddc88a1984deea287380c6f`, its five-path manifest, source-size and no-threshold boundary, supplied focused receipts, global size-audit limitation, and excluded non-green scanner result.

## Findings

No CRITICAL finding or unresolved HIGH finding remains in the S185 attestation.

### s185-count-labeling | high | Immutable source counts corrected

The initial execution record mixed a nonblank parent figure with a later live figure. The corrected record carries only source commit `adbdcc8875b9323b3ddc88a1984deea287380c6f`'s immutable physical comparison: 1373 parent `formula_runtime.py` lines, 1035 committed lines, and a new 363-line sibling.

### s185-size-audit-boundary | low | Global size audit is not green

The global size audit exits 1 for other subjects. It reports no `formula_runtime` offender, which is the only conclusion retained; the record does not claim a global pass.

### s185-scanner-boundary | low | Combined scanner result is excluded

The combined 25/4 scanner result is non-green and unattributed. It is expressly excluded from the S185 acceptance evidence rather than being assigned to this refactor.

### s185-focused-receipts | low | Focused evidence is executor-reported

The record preserves the three supplied focused outcomes and durations without inventing commands whose literal invocations were not supplied.

## Recommendations

- Re-run and independently attribute the non-green global size and combined scanner outcomes when the shared tree is stable; do not use them as S185 acceptance evidence.
