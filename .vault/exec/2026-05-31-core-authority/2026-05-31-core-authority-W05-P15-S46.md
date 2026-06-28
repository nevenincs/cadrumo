---
step_id: S46
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

# core-authority W05.P15.S46 — ApplicabilityVerdict placement audit (RENAME-011)

## Audit result

`ApplicabilityVerdict` is consumed by:
- `application/overview/__init__.py`, `_explain.py`, and 4 test files
- `entrypoints/cli/_modelo.py` and `test_modelo_202_modality.py`
- `domain/calculations/registry/applicability.py` (re-export shim)
- `domain/calculations/registry/test_modelo_applicability.py`

Rule 1(a) triggers because consumers span the application and entrypoints layers.

## Placement decision: stays in domain/calculations/registry/_applicability.py

The aeat-registry-authority-flow rule is explicit: registry types stay in the registry package unless consumed by more than one non-registry layer in a way that requires the type to be independent of the registry contract. `ApplicabilityVerdict` encodes AEAT-specific filing semantics (`ATTRIBUTION_PASS_THROUGH`, `INCOMPLETE`, etc.) that are definitionally part of the registry applicability engine. Promoting to `core/` would place domain logic in the infrastructure layer, violating hexagonal direction.

The `domain/calculations/registry/applicability.py` module (no leading underscore) is the declared re-export wall providing cross-layer public access. This is the architectural pattern the registry-authority-flow rule explicitly supports.

## Commit

`a5b5bf1fe` — docs(registry): S46 ApplicabilityVerdict placement audit - stays in domain/calculations/registry
