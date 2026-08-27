---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:ea69bb65d70ab5941ff1777f4e24718ca141b0fd8b4891ff5b7d8466eb40f394'
step_id: 'S297'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Add the modelo 184 socio per-member profile facts the accepted row-shape ADR requires: clave, subclave, and every clave/subclave-conditional fact this Step's scope covers (codigo-provincia, miembro-a-31-diciembre, dias-miembro, domicilio-fiscal, the clave-C inmueble sub-block [naturaleza-inmueble, situacion-inmueble, referencia-catastral, clave-declarado, porcentaje-titularidad-inmueble, dias-arrendamiento], the clave-C and clave-D reduccion amounts, and the clave-D subclave-03/04 rendimiento-neto fields), each enumerated and grounded directly against the socio record's own diseño field text -- not inferred from a field name. Excludes the clave-A reduccion (blocked pending citation), provisiones-gastos-dificil-justificacion (computed, not collected) and any clave-E eligibility fact (out of scope, tracked gap). Obtain real es/en/ca/hu strings for every new field before scaffolding -- no self-referencing placeholder value, no untranslated-identical entry without a stated reason

## Scope

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `the four locale catalogues under src/cadrumo/locales/`
- `and a focused schema-field coverage test asserting every new field resolves in all four languages`

## Changes

- `M` `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `M` `src/cadrumo/locales/es/profile.yml`
- `M` `src/cadrumo/locales/en/profile.yml`
- `M` `src/cadrumo/locales/ca/profile.yml`
- `M` `src/cadrumo/locales/hu/profile.yml`
- `M` `src/cadrumo/domain/user_profile/tests/test_attribution_entity_schema_fields.py`
- `A` `src/cadrumo/domain/user_profile/tests/test_m184_socio_clave_subclave_schema_fields.py`
- `verify:` `pytest src/cadrumo/domain/user_profile/` -> `pass, except two failures pre-existing and unrelated (see Notes)`
- `verify:` `python -m dev.locales scaffold --check` -> `fail, but the drift is 15 pre-existing peer CLI keys unrelated to this Step's fields`

## Notes

Two unrelated pre-existing failures were observed in the `user_profile` test
package and left untouched, per the standing rule to absorb only in-scope
regressions: `test_public_definition_inventory_is_exhaustive_and_identity_preserving[errors]`
(an `errors.py` `__all__` gap with zero working-tree diff on that file) and
`test_user_profile_defining_modules_import_before_registry_barrel` (a
subprocess import failure tracing to an in-flight, uncommitted peer edit at
`src/cadrumo/domain/iva/_place_of_supply.py`). Neither references this
Step's schema or locale changes.

`python -m dev.locales scaffold` also touched `cli.yml` and
`modelo/schema/200.yml` in all four locales as a tree-wide side effect of an
unrelated peer's in-progress CLI work; those files were left unstaged and
uncommitted, per the documented scaffold-is-tree-wide discipline.

The clave-C and clave-D reducción amounts are modelled as ONE `reduccion`
field, mirroring the diseño's own physical layout (positions 109-119 is a
single shared field whose meaning depends on the declared clave), rather
than two separate schema fields — the Step's action text names "the amounts"
plural because the field's value differs by which clave the row declares,
not because the diseño defines two physical fields.

`ca` and `hu` renderings for the 15 new field labels were authored directly
by this agent and would benefit from operator review.
