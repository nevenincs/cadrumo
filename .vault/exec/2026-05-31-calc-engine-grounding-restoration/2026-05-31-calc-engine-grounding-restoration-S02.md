---
tags:
  - "#exec"
  - "#calc-engine-grounding-swarm"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S02
related:
  - "[[2026-05-16-calc-engine-grounding-swarm-audit]]"
---

# calc-engine-grounding-restoration S02 — CRIT-2: ModeloCasillaProvenance missing formula_id

## Finding

Audit: `2026-05-16-calc-engine-grounding-swarm-audit` / task #566 CRIT-2.

`ModeloCasillaProvenance` in `domain/filing/_schema.py` had no `formula_id` field,
so filing drafts could not carry the formula identity for computed casillas.
The `casilla_provenance` builder in `application/filing/__init__.py` only populated
`legal_refs` and `source_refs`.

## Surface

`src/aeat/domain/filing/_schema.py` — `ModeloCasillaProvenance`.
`src/aeat/application/filing/__init__.py` — casilla_provenance builder.

## Fix

Added `formula_id: str | None = None` to `ModeloCasillaProvenance`. Updated the
casilla_provenance builder to pass `formula_id=casilla.formula` from
`CasillaDefinition.formula` (available at snapshot build time, type `FormulaId | None`).

## Tests

- `test_roundtrip_anti_tautology.py` — populated fixture with
  `formula_id="iva-cuota-devengada-formula"` (non-default) to catch save/load default regression.
- `test_secure_storage_roundtrip.py` — asserts `loaded.casilla_provenance[0].formula_id ==
  "iva-cuota-devengada-formula"` after encrypt/decrypt cycle.
- `test_export.py` — added `"formula_id": None` to expected provenance dict.

## Commit

`308f13db8` — `grounding(CRIT-2): add formula_id to ModeloCasillaProvenance`

## Status

Closed.
