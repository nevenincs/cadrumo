---
step_id: S60, S61
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
  - '[[2026-05-30-identity-primitives-reference]]'
---

# identity-primitives W04.P17 — lift filing schema and record design onto registry aliases

## Scope

Phase W04.P17 lifts the bare-string registry-id BaseModel
fields on `domain/filing/_schema.py` (S60) and inventories
the record-design surface (S61) per ADR Rule 8.

## Outcome

`src/aeat/domain/filing/_schema.py` — Step S60:
- Added registry alias import (`BindingId`, `CasillaId`)
  via `from ..calculations.registry._ids import ...`. This
  is a cross-domain import, but Rule 2 explicitly grants
  the registry-aliases exception.
- Lifted BaseModel fields:
  - `ModeloValue.casilla_id` → `CasillaId`
  - `ModeloBindingValue.binding_id` → `BindingId`
  - `ModeloCasillaProvenance.casilla_id` → `CasillaId`
  - `ModeloValidationFinding.casilla_id` → `CasillaId | None`

Step S61 — record-design surface scan:
`domain/calculations/registry/_record_design.py` carries
two pydantic models (`RecordDesignField`, `RecordDesignSheet`)
neither of which declares a registry-id field. The
`modelo_id` / `revision_id` survivors at lines 1636–1637
live on the `@dataclass(frozen=True) DisenoCoverageReport`
— out of Rule 9 clause 4 scope. S61 closed without code
changes.

## Verification

- Smoke imports clean on `domain/filing/_schema.py`.
- The four lifted sites are persistence-boundary fields on
  filing draft records (`ModeloDraft.values`, `.binding_values`,
  `.casilla_provenance`, `.findings`); the registry-pattern
  constraint now enforces at the load surface.

## Plan steps closed

`W04.P17.S60`, `W04.P17.S61`.

## Commits

- `b2a466b62` exec(identity-primitives): W04.P17.S60 lift
  filing schema registry-id BaseModel fields onto registry
  aliases
- (S61 closed without changes — record_design BaseModels
  carry no registry-id field; `DisenoCoverageReport` is a
  dataclass outside Rule 9 clause 4.)
