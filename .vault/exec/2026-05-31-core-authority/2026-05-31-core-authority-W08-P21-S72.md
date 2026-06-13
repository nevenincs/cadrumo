---
tags:
  - '#exec'
  - '#core-authority'
step_id: S72
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W08.P21.S72 - declare FiledDeclaracionObservationProtocol

## Outcome

Created `src/aeat/application/calculations/_ports.py` with three Protocols:

- `FiledDeclaracionArtefactProtocol` — minimal surface for artefact records
  (kind, sha256 properties).
- `ObservedCasillaValueProtocol` — minimal surface for casilla observations
  (source_artefact_kind, casilla_id, value properties).
- `FiledDeclaracionObservationProtocol` — structural interface for filed AEAT
  declaration observations, capturing the 9 attributes consumed by
  `iva_compensation_state_from_filed_observation` and `_decimal_casilla_values`
  in `_iva_compensation_history.py`.

All protocols are `@runtime_checkable`. The concrete `FiledDeclaracionObservation`
model from `adapters/outbound/aeat/sede/_schema.py` satisfies the protocol structurally.

MIGRATE-002, RELOC-017, Rule 8.

## Commit

`ebc3b641b` — refactor(calculations): W08.P21.S72+S73

## Files touched

- `src/aeat/application/calculations/_ports.py` — new

## Verification

10 IVA compensation tests pass.
