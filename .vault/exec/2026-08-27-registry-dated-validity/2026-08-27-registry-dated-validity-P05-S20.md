---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:dedb4a50efbc4d99ef295e497d7d70a8119f4d3d4d2c8832e0ec04b380c02375'
step_id: 'S20'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Derive the Art. 30.2.5.a insured population and its two limbs from the family profile, keeping membership and limb as separate questions and refusing the wider Art. 58.1 set that would admit a non-cohabiting dependent child and an over-25 child with discapacidad, and expose it beside the one canonical reconstruction of the family record from stored facts

## Scope

- `src/cadrumo/domain/contribuyente/ and src/cadrumo/application/modelo/profile_binding.py`

## Changes

- `A` `src/cadrumo/domain/contribuyente/_seguro_enfermedad_insured.py`
- `M` `src/cadrumo/domain/contribuyente/__init__.py`
- `M` `src/cadrumo/application/modelo/profile_binding.py`
- `A` `src/cadrumo/domain/contribuyente/tests/test_seguro_enfermedad_insured.py`
- `verify:` `pytest src/cadrumo/domain/contribuyente + profile-binding real path` -> `pass`

## Notes

NOT YET REACHABLE IN PRODUCTION, and recorded as unwired rather than done. The
counts are derived and correct, but the last hop into
application/aggregation/_renta_ledger.py is blocked by a CIRCULAR IMPORT:
application/modelo/profile_binding.py already imports from ..aggregation at line 79,
so the aggregation cannot import back to reach the family-profile assembler. A
function-local import would hide the cycle rather than remove it, which the runtime
import-graph audit axis names explicitly, so it was not used. The wiring edit was
written, found to cycle, and reverted; the tree carries no partial version of it.

Closing it needs _renta_family_profile_from_facts relocated out of application/modelo
into a layer both subpackages can depend on. That function's own docstring records it
as a deliberate single reconstruction carrying the union of two earlier ones, so the
relocation is delicate and deserves its own step rather than being folded in here.

THREE PLACES THE NEIGHBOURING PROVISION WOULD HAVE OVER-GRANTED, all avoided by
reading art. 30.2.5.a rather than reusing art. 58.1. Its household limb is
cohabitation OR assimilated economic dependency, where this article says only "que
convivan con el". Its age limb is under 25 OR any discapacidad, where this article
says only hijos menores de veinticinco anos -- so an over-25 child with discapacidad
is in the minimo population and outside this one. And the conyuge limb reads the
MARRIED status token, not the wider partnered set, because the article says "su
conyuge" and a pareja de hecho is not one.

An undeclared discapacidad grado takes the ORDINARY limb rather than dropping the
person. Membership is settled by then; only the limb is unknown, and the article
grants the ordinary limit absent the condition the higher one requires. Dropping them
would cost the filer 500 euros for a person the article covers.
