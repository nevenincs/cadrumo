---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-plan]]"
  - "[[2026-05-18-schema-hardening-research]]"
---

# `schema-hardening` audit: constraint-backfill candidates

## Outcome

Plan B's `pattern` / `min_length` / `max_length` / `enum` slots
landed structurally on `CasillaConstraints`. The Plan B steps
S11-S13 proposed three concrete retrofits (M100 CCAA, M720
domicilio, M232 clave-pais) but on inspection all three live at
the binding-selector level, not at `CasillaDefinition`:

- **M100 CCAA**: declared via binding `renta-2025-profile-tax-residence-ccaa`,
  not a casilla. The constraint slot belongs on the
  `BindingSelectorMap` typed model, not `CasillaConstraints`.
- **M720 domicilio**: declared at binding-selector
  `modelo-720-2013.type_2.251-414.domicilio-de-la-entidad-o-ubicacion-del-inmueble`
  with `selector.length = 164`. Length is enforced at the
  fichero-BOE serialiser, not at the casilla constraint surface.
- **M232 clave-pais**: declared at binding-selector level across
  five paraiso operation slots; same disposition as M720.

## Casilla-level constraint opportunities

After Plan A's typed `data_type` retrofits (NIF, year, period_code,
country_code, IBAN, name, nif_iva, ccaa_code, province_code,
postal_code, municipality_code, BIC, date), every casilla with an
enumerable or shape contract should have moved to the corresponding
typed alias rather than carrying redundant `constraints.pattern`
declarations. A casilla can still combine a typed `data_type` with
text constraints (e.g., a `data_type = "text"` casilla with a
narrow `enum`) but the corpus today has no such casilla.

## Structural value preserved

Plan B's framework remains a load-bearing extension:

- A future modeller adding a casilla with an enumerable text
  contract (e.g., a custom discriminator like
  `tipo_persona = "F" | "J"`) can now declare
  `constraints.enum = ("F", "J")` and have snapshot build enforce
  it.
- The `violates_text` method is available to consumers that
  resolve a casilla value into a string at evaluation time.
- The four new fields are documented and tested
  (`test_constraints_text_shape.py`, 19 tests).

## Backfill candidates: empty set

No casilla-level constraint backfill applied in Plan B P0X step
range. Plan C's semantic-role consistency validator will surface
divergent constraints across role-bound casillas; that is the
mechanism that turns text constraints into a load-bearing identity
property rather than a per-casilla declaration.

## Acceptance

Plan B P03's structural delivery (slots + validator + tests) is
the meaningful landing. Retrofits S11-S13 are documented as
binding-level deferrals; S14 remains as a sentinel for future
casilla-level enumerable contracts.
