---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:e343a0f5195195ff0fde608793e6eaabd279ee28b2bc6a08054356ce829e16a6'
step_id: 'S134'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Make the province-code alternation one declaration and route the postcode, province and INE municipality shapes through it, closing a registry boundary that accepted a nonexistent province

## Scope

- `src/cadrumo/core/spanish_postcode.py`
- `src/cadrumo/domain/calculations/registry/schema_scalars.py`
- `src/cadrumo/domain/calculations/registry/tests/test_long_tail_data_types.py`

## Changes

- `M` `src/cadrumo/core/spanish_postcode.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_scalars.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_long_tail_data_types.py`
- `verify:` `PostalCode` accepts `28001`/`01001`, refuses `99999`/`60000`/`00001`/`53000`
- `verify:` `MunicipalityCode` accepts `28079`, refuses `99999`/`00001`
- `verify:` `ProvinceCode` accepts `52`, refuses `99`
- `verify:` `ValidatedRegistryAuthority.load(...).validate_registry()` -> passes over the whole tree, 58 modelos
- `verify:` `pytest .../tests -k "long_tail or validate_scalar or data_type" -n 0 -m ""` -> `pass` (66)

## Notes

Two sentinels independently reported that the registry's `PostalCode` took any
five digits while `core/spanish_postcode.py` required a real province prefix, so
`99999` passed at one boundary and failed at the other. Both were right, and both
stopped one definition short of the actual finding.

`_PROVINCE_CODE_RE`, twenty lines above `_POSTAL_CODE_RE` in the SAME file, is
byte-identical to the alternation the core postcode pattern leads with. The file
already knew the province rule and its own postcode validator did not use it.
That is the third copy, and it is the one that makes the divergence look
accidental rather than considered.

So the merge is not "registry adopts the core postcode". The province alternation
is now its own named fragment in core, and three shapes read it: a province code
standing alone, a postcode, and an INE municipality code. The municipality code
is deliberately NOT collapsed into the postcode -- `28079` is Madrid the
municipality, not a postal district -- but it carries the same province prefix
and now says so by construction.

Checked before tightening, and neither sentinel did: whether any casilla
declaring `data_type = "postal_code"` is a FOREIGN address, which would make the
Spanish province rule wrong rather than stricter. All fourteen are Spanish -- M036
censo domicilios and locales, M180 rental property, M714 patrimonio. Modelo 210
does carry `irnr.contribuyente.foreign_address.postal_code`, but as an export
producer key, not under this data type.

Each validator keeps its own refusal and error type, as
`core/unit_proportion.py` already documents for its own family: only the SHAPE is
shared, because a caller loading a registry fragment must be told which fragment
is malformed.

`TestPostalCode::test_accepted` asserted `99999` and `00001` as valid postcodes,
and `TestMunicipalityCode::test_accepted` asserted `00001`. Corrected, and the
values moved to the refusal lists with the reason.
