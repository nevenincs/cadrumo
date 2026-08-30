---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:f7efeda30b038860997ffc24f38c41fae0e6b4808d78d03172e311ec8b85aa59'
step_id: 'S116'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Refuse a name imported from a namespace that exports nothing, the failure that has landed three times and takes a package down at collection rather than at use

## Scope

- `src/cadrumo/tests/test_inert_namespace_imports_resolve.py`

## Changes

- `A` `src/cadrumo/tests/test_inert_namespace_imports_resolve.py`
- `verify:` `pytest src/cadrumo/tests/test_inert_namespace_imports_resolve.py -n 0 -m ""` -> `pass`

## Notes

Judges only namespaces that serve NO names -- empty `__all__`, no `__getattr__`,
no re-exports. A first attempt read a live lazy export map as empty and reported
six thousand eight hundred false positives; narrowing to genuinely inert
namespaces leaves fifteen, of which ten were dunders and five were real.

Proved by planting an inert package and a consumer importing a name from it,
observing the refusal, then removing both. The probe files sat under `src/`,
which is the weaker form of the proof: the guidance prefers a probe outside the
repository so a peer's sweep cannot commit the mutation.
