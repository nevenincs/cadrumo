---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:b1749ff2481e4be7892077dd2506709e80b303f46dce9672cdaf5d92b1ada794'
step_id: 'S13'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Extend ProportionalityRule with dated statutory-cap rows so a cap the law re-fixes each ejercicio stops being a constant, make a cap either law-fixed or year-referenced but never both, refuse two amounts for one year, and intersect cap availability into the coverage derivation so the corpus cannot claim a year it can cite but not compute

## Scope

- `src/cadrumo/domain/categories/ and src/cadrumo/domain/categories/tests/`

## Changes

- `M` `src/cadrumo/domain/categories/_proportionality.py`
- `M` `src/cadrumo/domain/categories/_registry.py`
- `M` `src/cadrumo/_data/registry/aeat/categories/profiles.toml`
- `A` `src/cadrumo/domain/categories/tests/test_statutory_cap_schedule.py`
- `verify:` `pytest src/cadrumo/domain/categories` -> `pass`
