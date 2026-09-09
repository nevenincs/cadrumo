---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:725ba3c77fff0252517ba130d92db19a2cc5e04db54fe6a58463a850491a02c3'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# `facts-registry` `W02.P09` summary

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/convenio.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/modelo_projections.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_authority_enrollment.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_iva_rate_provider.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_iva_recargo_provider.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_modelo_projections.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_wave2_fact_provider_handoff.py`
- `A` `dev/registry/analysis/facts_wave2_provider_handoff.toml`
- `A` `dev/registry/tests/test_facts_wave2_provider_handoff.py`
- `M` `src/cadrumo/domain/categories/registry.py`
- `M` `src/cadrumo/domain/categories/tests/test_fact_provider.py`
- `M` `src/cadrumo/domain/deadlines/festivos.py`
- `M` `src/cadrumo/domain/deadlines/tests/test_fact_provider.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `verify:` `just check-types` -> `fail`
- `verify:` `just audit-dead-code` -> `pass`
- `verify:` `just audit-unreachable-code` -> `fail`

## Notes

Wave 2 introduced no remaining type or exact reachability finding. Repository-wide type and unused-symbol findings outside this campaign remain visible in the Step Records.
