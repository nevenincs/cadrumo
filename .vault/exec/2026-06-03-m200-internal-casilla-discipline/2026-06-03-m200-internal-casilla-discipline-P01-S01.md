---
tags:
  - '#exec'
  - '#m200-internal-casilla-discipline'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S01'
related:
  - "[[2026-06-03-m200-internal-casilla-discipline-plan]]"
  - "[[2026-06-03-m200-internal-casilla-discipline-adr]]"
---

# Add internal_only bool field to CasillaDefinition

## Scope

- `src/aeat/domain/calculations/registry/_schema.py`

## Description

Added `internal_only: bool = Field(default=False, description=...)` to `CasillaDefinition`. The description names the contract: an app-internal computed casilla participating in the calculation graph but intentionally absent from the AEAT-published Diseño de Registros, MUST be `input_kind = COMPUTED`, MUST carry no `export_refs`, and MUST carry grounded `legal_refs` / `source_refs`. Default `False` preserves every existing casilla declaration verbatim.

## Outcome

The field is on the model. Every TOML revision continues to load (default `False`); only the M200 `DP200014:bin-aplicada-maxima` flips it in P03.S06.
