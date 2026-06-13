---
tags:
  - '#exec'
  - '#core-authority'
step_id: S73
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W08.P21.S73 - remove FiledDeclaracionObservation adapter import

## Outcome

Removed `from ...adapters.outbound.aeat.sede import FiledDeclaracionObservation`
(line 13) from `application/calculations/_iva_compensation_history.py`. This was
the normal-scope application->adapters edge classified as RELOC-017.

Added import of `FiledDeclaracionObservationProtocol` from `._ports` (application-layer).
Replaced both type annotation uses of `FiledDeclaracionObservation` with the Protocol:
- `iva_compensation_state_from_filed_observation(observation: FiledDeclaracionObservationProtocol)`
- `_decimal_casilla_values(observation: FiledDeclaracionObservationProtocol)`

The concrete `FiledDeclaracionObservation` satisfies the protocol structurally; all 10
IVA compensation tests pass without change.

MIGRATE-002, RELOC-017, Rule 2, Rule 8.

## Commit

`ebc3b641b` — refactor(calculations): W08.P21.S72+S73

## Files touched

- `src/aeat/application/calculations/_iva_compensation_history.py` — removed adapter import

## Before / After

Before: 1 normal-scope application->adapters edge at `_iva_compensation_history.py:13`.
After: 0 module-level application->adapters edges in `_iva_compensation_history.py`.
(Persistence imports at lines 14 and 19 are addressed in S79.)

## Verification

10 IVA compensation tests pass. 90/91 calculations suite passes (1 pre-existing failure
in test_binding_prefill.py unrelated to this change).
