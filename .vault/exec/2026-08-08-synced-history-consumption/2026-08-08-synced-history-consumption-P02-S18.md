---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f5b7ea1d2210106a9219d9fb1c477bcb3536bf1a63265d6ada0dfee81eab68a2'
step_id: 'S18'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---
# Declare a treatment for the seventeen carries that have none, because an undeclared treatment cannot later be cited as authority for having consumed the value. Fifteen previous_filing bindings and both iva_compensation_annual_partition bindings are governed by no dependency classification at all, spanning Modelo 100 negative-base carry, Modelo 130 prior pagos and negative results, Modelo 131 negative results across four revisions, Modelo 353 prior Modelo 322 figures, Modelo 720 prior-year valuation baselines and Modelo 390's two compensacion partition slots. Each declaration is grounded in that row's own provisions and never by analogy to a sibling modelo, since AEAT surfaces do not transfer between modelos and a Modelo 720 valuation baseline and a Modelo 130 negative result are not the same kind of carry. Gate: every one of the seventeen carries a declared treatment with its own legal refs and source refs resolving in the legal catalogue, no two are justified by the same transferred rationale, and the registry loads clean.

## Scope

- Registry dependency classifications and construct membership for the twelve S18 carries.
- Generic direct-previous-filing closure validation and real mutation coverage.
- The affected command-sequence contracts and their CLI-generated goldens.

## Description

- Declare the twelve S18 source-modelo classifications from their own existing legal and source references.
- Associate every classification with the construct that owns its direct carry.
- Make the registry validator fail closed when a direct previous-filing source has no dependency-bearing classification, is relabelled `non_dependency`, lacks target coverage, or omits a required legal reference.
- Remove duplicate sequence setup where the canonical seed already supplies the invoice evidence, and resolve the quickstart attachment through the seeded expense lookup.
- Regenerate the fourteen affected goldens only through the sequence generator.

## Outcome

The loaded authority has no undeclared direct `previous_filing` carry. All fifteen carry declarations are present: twelve are owned by S18 across Modelo 100, Modelo 130, Modelo 131, and Modelo 720; three Modelo 353 declarations are separately owned by S35 and are included only in the full-authority result. The two Modelo 390 annual-partition bindings were already classified and were never part of the measured undeclared set.

The validator consumes the same source-modelo key as the previous-filing resolver, so it has one canonical failure path rather than a modelo-specific exception or parallel authority. The mutation suite proves both treatment kinds, missing relation-less direct-settlement classification, and `non_dependency` rejection.

## Verification

- Loaded `ValidatedRegistryAuthority` probe: all fifteen carries have exactly one source-modelo classification with construct and legal-reference coverage.
- `aeat app registry verify`: `Verificado=True`.
- Focused registry and resolver suite: 105 passed.
- Focused Ruff: all checks passed.
- All fourteen affected exact golden checks are clean: `first-quarter-export-file`, `modelo-130-first-quarter`, `irpf-lifecycle-q1`, `irpf-lifecycle-q2`, `modelo-130-export-file`, `modelo-130-inspect-boxes`, `modelo-130-manual-casilla`, `modelo-130-quarterly`, `modelo-130-review-chain`, `quickstart-modelo-130`, `quickstart-revision`, `review-values-bindings`, `review-values-manual-casilla`, and `review-values-review-saved`.
- Required first-quarterly-filing, Modelo 130, quickstart, and review-calculation-values page gates are clean.

## Review

Independent S18 code review is PASS. It found the missing direct-carry closure before approval; the generic validator and real mutation coverage resolved that finding. The remaining Modelo 720 work-unit/provenance observation is medium severity and non-blocking to the declared carry-treatment and generated-sequence scope.

## Notes

The broader IRPF-lifecycle page remains red for unrelated overview `target_command_key` and Notice drift. That is a global current-tree failure, not an S18 contract or generated-artifact failure, and it is excluded from this Step's closure claim.
