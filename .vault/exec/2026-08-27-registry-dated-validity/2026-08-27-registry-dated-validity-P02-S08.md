---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:48a63aa2ccc4e63fa4b84ba002df2e6bac23338d32fc4367b9a7527d2fded453'
step_id: 'S08'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Collapse the IVA place-of-supply groundings the same way, attaching the window to the rule rather than to a citation because the rule is the grounding-bearing row there, and checking it against the intersection of its legal_references' effective spans

## Scope

- `src/cadrumo/_data/registry/aeat/iva/ and src/cadrumo/domain/iva/`

## Changes

- `A` `src/cadrumo/_data/registry/aeat/iva/place_of_supply.toml`
- `D` `src/cadrumo/_data/registry/aeat/iva/place_of_supply/2025.toml`
- `M` `src/cadrumo/domain/iva/_place_of_supply.py`
- `M` `src/cadrumo/domain/iva/tests/test_place_of_supply_grounding.py`
- `M` `src/cadrumo/domain/iva/tests/test_iva_registry_grounding.py`
- `verify:` `pytest src/cadrumo/domain/iva` -> `pass`
