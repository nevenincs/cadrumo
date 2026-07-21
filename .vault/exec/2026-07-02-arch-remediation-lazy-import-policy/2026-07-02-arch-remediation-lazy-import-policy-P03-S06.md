---
tags:
  - '#exec'
  - '#arch-remediation-lazy-import-policy'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S06'
related:
  - "[[2026-07-02-arch-remediation-lazy-import-policy-plan]]"
---

# Add the grimp runtime-graph pass as a documented axis in the swarm-audit cadence rule at its vaultspec source and run vaultspec-core sync, so the executed import graph is re-measured on the standing structural-audit rhythm

## Scope

- `.vaultspec/rules/aeat-swarm-audit-cadence.md`

## Description

- Add the runtime import-graph coupling pass as the eighth documented axis in the swarm-audit cadence rule at its vaultspec source (`.vaultspec/rules/aeat-swarm-audit-cadence.md`): a grimp pass over the executed import graph, diffed against the static import-linter graph to surface hidden cross-layer edges and module cycles the function-local-import idiom conceals.
- Ground the axis against the D7 lazy-import policy gate: the gate's allowlist is the declared inventory of unsanctioned function-local first-party edges, so a grimp-discovered runtime edge with no allowlist entry (or an unexplained new cycle) is the actionable finding.
- Add the axis to the axis enumeration and the model-matching guidance (breadth-oriented, haiku), then run `vaultspec-core sync`.

## Outcome

The rule now documents eight standing axes. `vaultspec-core sync` regenerated the four provider copies (claude, gemini, antigravity, codex) from the source; each carries only the grimp-axis change.

## Notes

Edited the vaultspec source and propagated with sync per the centralisation discipline; the generated provider directories were not hand-edited.
