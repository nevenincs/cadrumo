---
tags:
  - '#plan'
  - '#modelo-200-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-28-modelo-200-calc-verify-adr]]"
  - "[[2026-04-28-modelo-200-calc-verify-research]]"
---

# `modelo-200-calc-verify` implementation plan

Implement the accepted annual page-14 M200 strategy from the ADR and verify it against the Tier-L safety invariants.

## Proposed Changes

- Refactor the 2024 M200 ruleset to expose helper builders for casillas and formulas.
- Add `modelo_200.2025` and `modelo_200.2026` with non-overlapping annual effective windows.
- Register both rulesets in the concrete ruleset registry.
- Expand worked-example tests for 2024, 2025, and 2026, including tax-rate split scenarios.
- Update registry, CLI listing, smoke, zero-boundary, scalar mutation, operand-swap mutation, and mutation kill-rate tests.
- Change M200 integration import tests from unverifiable to verified and add the discrepancy classifier case.
- Add the rule-delta manifest and execution summary.
- Flip the M200 coverage row to verified once local verification passes.

## Tasks

- Rulesets: add 2025 and 2026 annual files and registry exports.
- Formula tests: add cent-exact cases for every computed casilla and rate-split examples.
- Roundtrip tests: keep the v2025 extractor surface and verify complete, partial, and tampered synthetic PDFs.
- Mutation tests: enumerate new M200 sub-op and scalar nodes.
- Documentation: persist source inventory, year deltas, scope decisions, and citation audit output.
- Review: run formal code review against changed files and issue invariants.

## Parallelization

Implementation is mostly serial because registry exports and mutation fixtures depend on the ruleset names. Documentation and review can run after the first focused green test pass.

## Verification

Required checks:

- `uv run pytest` on the M200 ruleset tests, registry/listing tests, and M200 integration class.
- `uv run pytest` on scalar mutation, operand-swap mutation, mutation kill-rate, mutator exhaustiveness, and zero-boundary coverage.
- `uv run aeat audit rulesets citations`.
- `just lint`, `just typecheck`, `just test`, and `just hooks` before final handoff.
