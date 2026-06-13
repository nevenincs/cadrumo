---
tags:
  - '#plan'
  - '#modelo-131-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-131-calc-verify-adr]]"
  - "[[2026-04-27-modelo-131-calc-verify-research]]"
---



# modelo-131-calc-verify plan

Implement the Modelo 131 Tier-L calc-verify surface for 2024, 2025, and 2026.

## Proposed Changes

- Add and register the 2026 annual ruleset.
- Add per-year worked examples for the six computed M131 casillas.
- Extend registry, CLI list, zero-boundary, percent-rate, operand-swap, and mutation catalogue expectations.
- Record the 2024 to 2026 rule delta and L1 anchor waiver.
- Update the coverage matrix for Modelo 131.

## Tasks

- Completed: BOE source check for RD 439/2007, Orden EHA/672/2007, Orden HFP/1359/2023, Orden HAC/1347/2024, and Orden HAC/1425/2025.
- Completed: 2026 ruleset authoring and registry/list integration.
- Completed: worked-example and mutation-harness coverage.
- Completed: coverage documentation and vault reference update.
- Pending: full lint, typecheck, test, hooks, and final code review.

## Parallelization

Ruleset and test updates are tightly coupled through registry enumeration, so implementation is mostly serial. Documentation review can run after focused tests pass.

## Verification

- `aeat audit rulesets citations` reports 100% for M131 2024, 2025, and 2026.
- Focused M131/ruleset/registry/mutation tests pass.
- `just lint`, `just typecheck`, `just test`, and `just hooks` pass before final handoff.
- Code review records no high-severity findings.
