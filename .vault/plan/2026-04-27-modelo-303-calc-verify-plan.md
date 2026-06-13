---
tags:
  - '#plan'
  - '#modelo-303-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-303-calc-verify-research]]"
  - "[[2026-04-27-modelo-303-calc-verify-adr]]"
  - "[[2026-04-27-modelo-303-rule-delta-reference]]"
---

# `modelo-303-calc-verify` implementation plan

Modelo 303 reaches the Tier-L calc-verify-roundtrip bar by registering a 2026 scoped régimen-general ruleset, extending extractor resolution to 2026, documenting the 2024 to 2026 delta, and proving the ruleset through per-year tests, mutation harnesses, and Kent CLI integration.

## Proposed Changes

Add a new 2026 ruleset file for Modelo 303, registered in the formulas ruleset registry. Keep the formula graph structurally identical to 2024 / 2025 because the represented LIVA art. 90 / 91 rate surface is unchanged.

Add a 2026 extractor subclass that reuses the existing 33-casilla v2025 extraction logic with a 2026 template revision. Keep the generator unchanged because it already emits all M303 liquidación casillas.

Extend tests and mutation harness expectations so the new ruleset is explicitly exercised rather than only reachable through registry smoke coverage.

Author the vault research, ADR, plan, execution summary, rule-delta manifest, and L1 anchor waiver. Update `docs/coverage/modelos.md` for the M303 2026 closure.

## Tasks

- Ruleset and registry
  1. Add `modelo_303.2026` with a 2026 effective window.
  2. Register `MODELO_303_2026` in `ALL_RULESETS` and public ruleset exports.
  3. Update registry and CLI listing tests.
- Worked examples and mutation
  1. Add 2026 worked-example tests for rate buckets, deductible totals, attribution, compensation, and negative discrepancy behavior.
  2. Add M303 2026 rows to percent-rate, operand-swap, scalar-leaf, and kill-rate mutation harnesses.
- Extractor and integration
  1. Add `Modelo303V2026Extractor`.
  2. Add parser coverage for a 2026 synthetic M303 PDF.
  3. Add a 2026 Kent CLI happy-path case.
- Documentation
  1. Add rule-delta and L1 waiver reference files.
  2. Record execution evidence.
  3. Update the coverage matrix provenance.

## Parallelization

Ruleset/test work and vault documentation can run in parallel after the BOE source boundary is fixed. Extractor and integration changes depend on the 2026 ruleset registration so `verify_declaracion` can resolve the 2026 period.

## Verification

Focused verification:

- `uv run pytest src/aeat/domain/formulas/_rulesets/test_modelo_303_2026.py src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py src/aeat/adapters/inbound/declaracion/test_modelo_303_v2025.py tests/integration/test_kent_workflows.py::TestKentImportsModelo303Declaracion src/aeat/domain/formulas/test_registry.py src/aeat/domain/formulas/test_cli.py src/aeat/domain/formulas/test_smoke.py`
- `uv run aeat audit rulesets citations`

Full gates:

- `just lint`
- `just typecheck`
- `just test`
- `just hooks`
- `just test-cov`

## Self-Review

Plan self-review completed against the issue body, project mandates, the M130 reference implementation, and no-mocks discipline.

Cent-exact verification is covered by 2026 rate-bucket rounding tests and by the existing formula engine's terminal two-decimal rounding. Expected values are externally anchored to LIVA arts. 90 and 91 and Modelo 303 form arithmetic, not copied from the `ParameterTable`.

The 2026 franquicia rule is explicitly scoped out of this base M303 ruleset. Available BOE/AEAT context indicates separate/future small-enterprise surfaces rather than a current change to the scoped 33-casilla régimen-general DAG.
