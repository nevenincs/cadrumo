---
step_id: S48
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W05.P15.S48 — CENSUS_MODELO_SERVICE_OWNER placement audit (RENAME-013)

## Audit result

`CENSUS_MODELO_SERVICE_OWNER = "aeat.domain.calculations.registry"` is consumed only within:
- `_censo_modelos.py` — as `Field(default=CENSUS_MODELO_SERVICE_OWNER, pattern=r"^aeat\.domain\.calculations\.registry$")` and a `model_validator`
- `test_census_modelo_foundation.py` — same package
- `__init__.py` — re-export only (no external consumers found)

Zero consumers in `application/`, `entrypoints/`, or `adapters/`.

## Placement decision: stays in domain/calculations/registry/_censo_modelos.py

ADR Rule 6 restricts `core/external_constants.py` to external AEAT endpoint URLs, regulatory thresholds (Decimal), encoding labels, and cross-service identifiers. A service-ownership token encoding a Python module path is a registry-internal constraint, not an external constant. Moving it to `core/` would introduce domain module-path knowledge into the infrastructure layer, creating a core-to-domain coupling that Rule 1 prohibits.

## Commit

`04cf0bbea` — docs(registry): S48 CENSUS_MODELO_SERVICE_OWNER placement audit - stays in _censo_modelos
