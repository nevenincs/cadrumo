---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:809f05c4a7503307c9476935f343b45483a0b268a6529619f7a500213eb6862f'
step_id: 'S07'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Collapse the IVA regulation catalogue into one undated file with a required ValidityWindow on every citation authored from the cited provision's effective span, derive covered years from those windows, preserve the exact-year refusal, and delete the year-named file and its filename-year loader branch outright

## Scope

- `src/cadrumo/_data/registry/aeat/iva/ and src/cadrumo/domain/iva/`

## Changes

- `A` `src/cadrumo/_data/registry/aeat/iva/catalogues.toml`
- `D` `src/cadrumo/_data/registry/aeat/iva/catalogues/2025.toml`
- `M` `src/cadrumo/domain/iva/_schema.py`
- `M` `src/cadrumo/domain/iva/_catalogue.py`
- `M` `src/cadrumo/domain/iva/__init__.py`
- `M` `src/cadrumo/core/config.py`
- `M` `src/cadrumo/core/_storage_taxonomy.py`
- `M` `src/cadrumo/core/resources/_registry.py`
- `M` `src/cadrumo/core/resources/_repos/iva_catalogues.py`
- `M` `src/cadrumo/domain/iva/tests/test_catalogue_period_keyed.py`
- `M` `src/cadrumo/domain/iva/tests/test_rules.py`
- `M` `src/cadrumo/domain/iva/tests/test_verify.py`
- `M` `src/cadrumo/domain/iva/tests/test_lookup_refusals_carry_no_authored_prose.py`
- `M` `env/.env.example`
- `M` `docs/reference/environment-overrides.md`
- `verify:` `pytest src/cadrumo/domain/iva` -> `pass`
