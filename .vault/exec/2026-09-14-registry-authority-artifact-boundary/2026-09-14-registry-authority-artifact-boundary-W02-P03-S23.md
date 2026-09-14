---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:49aeb17e8e1d14aa33f860f01782f7e4b79d32252d1ea12d7ca90f8d7cfba441'
step_id: 'S23'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Resolve requested facts and preserve exact temporal, selector, precedence and provenance semantics without whole-catalogue hydration

## Scope

- `src/cadrumo/domain/calculations/registry/facts/resolution.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/iva/lookup.py`
- `M` `src/cadrumo/domain/iva/rates.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_rates_temporal.py -q` -> `pass`
