---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:f8505cd38c6e5e118fbe19305ccf269e79630983cef91981a3fe31df76020748'
step_id: 'S46'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Run canonical strict production type checking at the Wave 2 handoff

## Scope

- `justfile check-types and dev/quality/types.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/convenio.py`
- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_iva_rate_provider.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_iva_recargo_provider.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_modelo_projections.py`
- `M` `src/cadrumo/domain/categories/tests/test_fact_provider.py`
- `M` `src/cadrumo/domain/deadlines/tests/test_fact_provider.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W02-P09-S46.md`
- `verify:` `just check-types` -> `fail`

## Notes

Wave 2's 12 type diagnostics were fixed. The final boundary run reports diagnostics outside the facts-registry campaign while concurrent repository work is active; no Wave 2 provider path remains in the detailed result.
