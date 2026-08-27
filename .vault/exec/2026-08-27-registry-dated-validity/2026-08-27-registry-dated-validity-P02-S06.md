---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:2f9b1c47973311c6b804bb86264616903678820c53e2ef41db8625a335652a3c'
step_id: 'S06'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Add the provision-window gate refusing any grounded row whose validity window reaches outside the intersection of its cited provisions' own effective spans in the registry legal catalogue, so the permissible span is derived from the catalogue rather than attested by the author, and fails closed on a provision repealed or effective mid-window

## Scope

- `src/cadrumo/domain/iva/tests/`

## Changes

- `A` `src/cadrumo/domain/iva/tests/test_provision_window_bounds_grounding.py`
- `verify:` `pytest src/cadrumo/domain/iva/tests/test_provision_window_bounds_grounding.py` -> `pass`
