---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:1b24832aaa54729fa94cc83c5082ee54fd0a76585a813a3d775414a99def0cb0'
step_id: 'S03'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Collapse the two spending-category profile years into one undated file carrying a required ValidityWindow on every citation, drop the forty-one mirrored 2024 citations rather than re-windowing them, derive covered years from the citation windows, preserve the exact-year refusal unchanged, update every consumer and fixture, and delete the year-named files and their tests outright in the same commit

## Scope

- `src/cadrumo/_data/registry/aeat/categories/ and src/cadrumo/domain/categories/`

## Changes

- `A` `src/cadrumo/_data/registry/aeat/categories/profiles.toml`
- `D` `src/cadrumo/_data/registry/aeat/categories/profiles/2024.toml`
- `D` `src/cadrumo/_data/registry/aeat/categories/profiles/2025.toml`
- `M` `src/cadrumo/domain/categories/_proportionality.py`
- `M` `src/cadrumo/domain/categories/_registry.py`
- `M` `src/cadrumo/domain/categories/__init__.py`
- `M` `src/cadrumo/domain/categories/tests/test_registry.py`
- `M` `src/cadrumo/domain/categories/tests/test_profile.py`
- `M` `src/cadrumo/domain/categories/tests/test_proportionality.py`
- `M` `src/cadrumo/domain/categories/tests/test_citation_authority.py`
- `M` `src/cadrumo/domain/usage_ratios/_model.py`
- `M` `src/cadrumo/domain/renta/tests/test_ledger_expenses.py`
- `M` `src/cadrumo/domain/renta/tests/test_region_deductibility_selection.py`
- `M` `src/cadrumo/application/aggregation/tests/test_renta_ledger.py`
- `M` `dev/locales/_registry_scanner.py`
- `M` `dev/ci/tests/test_ledger_scale_benchmark.py`
- `verify:` `pytest src/cadrumo/domain/categories src/cadrumo/domain/renta/tests` -> `pass`
