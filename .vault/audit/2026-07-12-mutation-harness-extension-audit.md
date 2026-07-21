---
tags:
  - '#audit'
  - '#mutation-harness-extension'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-04-25-mutation-harness-extension-plan]]"
  - "[[2026-04-25-mutation-harness-extension-adr]]"
  - "[[2026-04-29-mutation-harness-fix-adr]]"
---

# `mutation-harness-extension` audit: `legacy plan supersession reconciliation`

## Scope

Reconcile the unchecked April mutation-harness checklist against its execution
summary, the later mutation-harness fix, and the current registry-calculation
architecture.

## Findings

### retired-ruleset-mutation-suite | low | all ten rows target an architecture that no longer exists

The original execution summary records delivery of the percent-rate, brackets,
scalar, operand-swap, exhaustiveness, and kill-rate harnesses. The later
accepted mutation-harness fix then repaired its empirical kill-rate contract
and documented its genuine deferred cases.

Current inspection confirms `src/aeat/domain/formulas` no longer exists. The
ruleset AST and its mutation modules were retired in favour of revision-backed
TOML formulas and the registry formula runtime under
`src/aeat/domain/calculations/registry`. Reopening the old plan would restore a
parallel formula authority and obsolete test topology; it cannot be treated as
an active quality gap.

The plan's coverage percentage, runtime-generated execution summary, and
project-wide gate wording are historical evidence only. Current registry tests
and formula-validation gates own calculation quality. No unchecked row remains
actionable under the current architecture.

## Recommendations

- Resolve every legacy checklist row as delivered and superseded. Retain the
  original and fix execution records as historical evidence.
- If mutation analysis is needed for the registry runtime later, start a new
  research and ADR cycle grounded in TOML revision formulas; do not revive this
  removed AST harness.
