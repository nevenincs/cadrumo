---
step_id: S54
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W03.P13.S54 — tighten sede casilla_id to CasillaId

## Scope

Replace the permissive
`casilla_id: str = Field(min_length=1, max_length=128,
pattern=r"^[0-9A-Za-z_.-]+$")` declaration on
`ObservedCasillaValue` in
`src/aeat/adapters/outbound/aeat/sede/_schema.py` with the typed
`CasillaId` alias from `domain/calculations/registry/_ids.py` per
ADR Rule 8.

The new pattern is strictly tighter: leading character must be
alphanumeric, body characters must match
`^[A-Za-z0-9][A-Za-z0-9._:-]*$`, max length drops from 128 to 64.

## Outcome

`src/aeat/adapters/outbound/aeat/sede/_schema.py`:
- New import:
  `from .....domain.calculations.registry._ids import CasillaId`.
- `ObservedCasillaValue.casilla_id: CasillaId`.

## Verification

- Probed CasillaId with the observed casilla shapes (numeric `15`,
  `120`, dotted `iva.cuota-devengada-total`,
  `iva.cuota-deducible-total`): all validate cleanly.
- Two declaration-PDF test failures
  (`TestDeclaracionPdfObservation::test_declaration_pdf_values_become_observed_casillas`,
  `test_modelo_111_declaration_pdf_values_become_observed_casillas`)
  reproduce identically with the original `Field(...)` declaration
  restored. The failures originate in the PDF-extraction pipeline
  ("did not yield casilla observations"), not in the schema
  tightening, and are pre-existing on this branch.

## Plan steps closed

`W03.P13.S54`.
