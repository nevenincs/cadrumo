---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:5ee5032aa71ea0bf076355ce768d7d44c2bde8de070b2176f0eb615d3c9fad50'
step_id: 'S08'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Narrow previous-filing, prorrata, bienes-inversion and iva-compensation resolvers on typed provider members and delete the Mapping-or-attr dual reads

## Scope

- `src/cadrumo/application/modelo/binding_prefill.py`
- `src/cadrumo/application/calculations/prorrata_regularizacion.py`
- `src/cadrumo/application/calculations/bienes_inversion_regularizacion.py`
- `src/cadrumo/application/aggregation/_per_grupo_member_keys.py`

## Changes

- `M` `src/cadrumo/application/calculations/binding_prefill.py`
- `M` `src/cadrumo/application/calculations/prorrata_regularizacion.py`
- `M` `src/cadrumo/application/calculations/_per_grupo_member_keys.py`
- `verify:` `uv run ruff check <touched>` -> `pass`
- `verify:` `uv run ty check <touched>` -> `pass`
- `verify:` `uv run basedpyright <touched>` -> `pass`

## Notes

The Step row names `src/cadrumo/application/modelo/binding_prefill.py` and
`src/cadrumo/application/aggregation/_per_grupo_member_keys.py`; the live
modules are `application/calculations/binding_prefill.py` and
`application/calculations/_per_grupo_member_keys.py`.

`bienes_inversion_regularizacion.py` and the iva-compensation resolver carried
no untyped selector read and were left unchanged.

`binding_prefill.py` also moved its `M303_COMPENSATION_*` imports to
`domain/calculations/registry/iva_compensation_annual_partition_bindings.py`,
the constants' new defining module.

Deleting the untyped selector guards orphaned three translation keys
(`selector_filing_year_delta_type`, `selector_source_periods_type`,
`selector_source_periods_member_type`) in the `ca`, `en`, `es` and `hu`
application catalogues. They were left in place: the locale sources are under
concurrent edit by another writer.

Repository test suites for these modules cannot run: the published authority
artifact is mid-regeneration and fails validation in an autouse fixture.
Behaviour was verified by direct execution of the typed narrows instead.
