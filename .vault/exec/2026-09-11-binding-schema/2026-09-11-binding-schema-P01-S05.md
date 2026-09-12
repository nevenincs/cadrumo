---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:6582c7dfec7b8dcc68719cb32590b1cb40e370bba6bef4ef74591b3728343028'
step_id: 'S05'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Add compiler refusals for unregistered kinds, missing model, validator or route, channel, aggregation and cardinality mismatches, unadmitted terminal origins, absolute temporal coordinates, and alternates whose value contract differs from the primary

## Scope

- `dev/registry/compiler/validate_bindings.py`
- `dev/registry/compiler/_validate_record_sections.py`
- `dev/registry/compiler/tests/`

## Changes

- `A` `dev/registry/compiler/validate_bindings.py`
- `M` `dev/registry/compiler/_validate_revision_sections.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_targets.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `A` `dev/registry/tests/test_validate_bindings.py`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_validate_bindings.py -n 0` -> `pass`
- `verify:` `uv run --no-sync ty check` (touched files) -> `pass`
- `verify:` `uv run --no-sync basedpyright` (touched files) -> `pass`
- `verify:` `uv run --no-sync ruff check` / `ruff format` (touched files) -> `pass`

## Notes

The unreferenced-binding refusal is enrolled as an advisory
(`unreferenced_binding_advisories`), not as a compiler failure: measured across
every currently loadable modelo it reports 299 rows, so refusing would break the
corpus. `_validate_record_sections.py` and `_validate_previous_filing_sources.py`
were inspected and needed no edit; the registration section is enrolled in
`_validate_revision_sections.py` instead.
