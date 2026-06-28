---
tags:
  - '#plan'
  - '#modelo-123-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-modelo-123-calc-verify-research]]'
  - '[[2026-04-27-modelo-123-calc-verify-adr]]'
---

# `modelo-123-calc-verify` implementation plan

Deliver Modelo 123 calc-verify-roundtrip coverage for 2024, 2025, and 2026
without expanding the ruleset beyond declaration-level aggregation.

## Proposed Changes

Add a 2026 ruleset, register it, and preserve the existing formula surface:
`03 = 01 + 02`, `06 = 04 + 05`, `09 = 07 + 08`, and `11 = 09 - 10`.

Extend the declaration extractor registry so 2024, 2025, and 2026 M123
synthetic declaration PDFs all parse through the same 11-casilla layout.

Backfill per-year worked examples, registry assertions, mutation catalogue
expectations, and Kent CLI integration coverage. Update the coverage matrix
and rule-delta reference to document the aggregation-only boundary and the
L1 public-anchor waiver.

## Tasks

- Add and register `modelo_123.2026`.
- Extend `Modelo123V2025Extractor` with 2024 and 2026 sibling classes.
- Add per-year M123 worked examples and no-drift tests.
- Update registry, smoke, CLI, zero-boundary, and mutation harness tests.
- Extend `TestKentImportsModelo123Declaracion` with a per-year happy path.
- Add `.vault/reference/2026-04-27-modelo-123-rule-delta-reference.md` and exec summary evidence.
- Update `docs/coverage/modelos.md` M123 row and provenance.

## Parallelization

The source and test edits are tightly coupled through registries and explicit
enumeration tests, so implementation should be integrated in one pass. The
documentation research/authoring workflow can run in parallel and be applied
after focused tests pass.

## Verification

Run focused ruleset, extractor, mutation, and Kent integration tests first.
Then run `aeat audit rulesets citations` to confirm 100% M123 citation
coverage. Finish with lint, typecheck, full tests, hooks, and vault checks.
