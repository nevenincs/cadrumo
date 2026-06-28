---
tags:
  - '#plan'
  - '#modelo-180-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-28-modelo-180-calc-verify-research]]"
  - "[[2026-04-28-modelo-180-calc-verify-adr]]"
  - "[[2026-04-28-modelo-180-calc-verify-reference]]"
---

# `modelo-180-calc-verify` implementation plan

## Proposed Changes

Complete Modelo 180 calc-verify coverage for 2024, 2025, and 2026 while preserving the legally scoped rental-withholding surface. The implementation will add a 2026 ruleset, register year-specific extractor support, add deterministic annual cumulation from four Modelo 115-style quarters, extend focused tests and mutation enumeration, update coverage docs, and record execution evidence.

## Tasks

- Add ruleset and registry coverage:
  - Create the 2026 ruleset with 2026 effective dates.
  - Register `MODELO_180_2026`.
  - Keep 2024/2025 formulas citation-clean.
- Add extractor and CLI coverage:
  - Add 2024 and 2026 extractor siblings.
  - Extend Kent M180 integration tests over 2024/2025/2026.
- Add formula and cumulation tests:
  - Add 2024 tests.
  - Extend 2025 tests with cumulation.
  - Add 2026 tests with no-drift and BOE-anchored worked examples.
  - Extend mutation expected counts and percent-rate cases.
- Add documentation and evidence:
  - Write the rule-delta manifest.
  - Update the coverage matrix.
  - Record citation, mutation, and focused test evidence.
  - Run mandatory code review.

## Parallelization

The code changes are small and coupled through registry imports, so local serial execution is safer than splitting implementation. Review can run after focused verification and before final full checks.

## Verification

Required checks:

- Focused ruleset tests for M180 2024/2025/2026.
- Kent CLI integration class for M180.
- Percent-rate mutation harness and mutator kill-rate aggregation.
- `aeat audit rulesets citations`.
- `just lint`, `just typecheck`, `just test`, and `just hooks` before final handoff if runtime permits.
