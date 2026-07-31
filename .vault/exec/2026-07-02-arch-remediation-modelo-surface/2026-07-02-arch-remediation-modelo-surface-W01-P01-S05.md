---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:7f57cb2b866daad545ee86ad3d6edb1d9df11f63061ee56d2daaeb9fa2c37064'
step_id: 'S05'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Sweep every consumer of the calculation result to read the typed unresolved-outcome channel, confirming no site still inspects reserved negative Decimals

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Sweep calculation-result consumers for M210 sentinel inspection.
- Confirm `calculate_modelo_revision` continues to consume `values`, `entries`, and typed observations without sentinel assumptions.
- Confirm no source path still imports or checks the removed sentinel symbols.

## Outcome

The calculation-result consumer sweep found no remaining reserved-negative-Decimal inspections.

## Notes

`rg` for `M210_CONVENIO_MISSING_SENTINEL`, `M210_DEFERRED_TIPO_SENTINEL`, `M210_RATE_SENTINELS`, and `_rewrite_m210_sentinels` returned no `src` matches.

## Follow-on completion (persistence of the typed outcome)

The initial W01 landing wired the verify consumer (S04) to read
`target.unresolved_outcomes` from the persisted `CalculationRevision`, but the
persistence channel that carries the engine's `unresolved_outcomes` onto the
revision was not part of that change, leaving the committed verify path reading a
field the persisted record did not yet declare. This follow-on completes the
calculation-result consumer sweep: `CalculationRevision` gains a typed
`unresolved_outcomes` tuple (parallel to `observations`, deliberately NOT threaded
into `derive_calculation_revision_id`), `persist_calculation_revision` accepts and
stores it, and `calculate_modelo_revision` passes `engine_result.unresolved_outcomes`
through. The encrypted-boundary roundtrip fixture now populates the field
non-default so a save-drops-field regression surfaces. With this in place the S04
verify consumer reads a genuinely persisted channel end to end.
