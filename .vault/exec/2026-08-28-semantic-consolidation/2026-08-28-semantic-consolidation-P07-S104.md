---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:3987001b75a450328368374c16ea855fe1d25ebeeef08577d8be1f8a913e2b25'
step_id: 'S104'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the module-level re-export facade in calculation_revision, where thirteen names were imported solely to be listed in its __all__ and reached that way by thirty-two consumers

## Scope

- `src/cadrumo/domain/modelos/calculation_revision.py`

## Changes

- `M` `src/cadrumo/domain/modelos/calculation_revision.py`
- `M` 32 consumer modules across `src/cadrumo/`
- `verify:` `pytest src/cadrumo/domain/modelos -n 0 -m unit` -> `pass` (245)

## Notes

A first pass over-collected: names appearing exactly twice were treated as pure
re-exports, but six of the nineteen appear twice because they are used once in
the body -- `ModeloError` as a base class among them. Those were restored and
the criterion narrowed to names that appear only in the import and in `__all__`.
