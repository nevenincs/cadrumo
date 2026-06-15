---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S15'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# wire the per-family unrouted-observation advisory diagnostics on the live calculate path so a resolver surfaces an advisory instead of a silent Decimal(0)

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Locate the IVA screen's live caller: the IVA mesh resolver already projects unrouted IVA observations into `CalculationSourceDiagnostic` advisories on each resolve.
- Wire the renta-expense and renta-income screens onto their resolvers in `_modelo_bindings.py`, emitting one `unrouted_observation` advisory per unrouted observation through the same diagnostics channel.
- Wire the OSS screen onto its resolver in `_oss_ioss.py`, emitting the advisory for the candidate-present case (the no-live-source case keeps its existing `oss_no_live_source` advisory).
- Align the existing IVA unconsumed-observation diagnostic from `source_issue` to the new `unrouted_observation` reason for uniformity across families.

## Outcome

Every live aggregation family now surfaces an advisory (non-blocking) `CalculationSourceDiagnostic` on the calculate path when a non-zero declarable observation routes to no binding, instead of silently resolving the casilla to zero. Calculate still succeeds; the diagnostic rides the shared mesh diagnostics channel.

## Notes

The advisory is emitted, never swallowed. The reason rename on the IVA diagnostic is safe: the existing IVA test filters on `source_kind` plus message substring, not the reason string.
