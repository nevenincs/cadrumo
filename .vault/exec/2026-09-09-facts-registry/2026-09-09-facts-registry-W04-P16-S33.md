---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:950bcd554218f8660c00feca355e83d8967907b9093cc23290663e3f3a177daa'
step_id: 'S33'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Replace the remaining technical model-routing aliases with their specialized aggregation and calendar-policy owners, then delete the aliases

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py and src/cadrumo/application/overview/calendar_warnings.py and src/cadrumo/core/external_constants.py and dev/registry/analysis/facts_external_constants_retirement.toml and dev/registry/tests`

## Changes

- `A` `.vault/audit/2026-09-11-facts-registry-s33-routing-retirement-audit.md`
- `M` `.vault/index/facts-registry.index.md`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `M` `dev/registry/analysis/facts_external_constants_retirement.toml`
- `M` `dev/registry/tests/test_applicability_fragment_family.py`
- `M` `dev/registry/tests/test_facts_external_constants_retirement.py`
- `M` `src/cadrumo/application/aggregation/__init__.py`
- `R` `src/cadrumo/application/aggregation/_modelo_bindings_retenciones.py` -> `src/cadrumo/application/aggregation/modelo_bindings_retenciones.py`
- `M` `src/cadrumo/application/aggregation/_retenciones.py`
- `M` `src/cadrumo/application/aggregation/_service.py`
- `M` `src/cadrumo/application/aggregation/_withholding_source.py`
- `M` `src/cadrumo/application/aggregation/tests/test_per_modelo_service.py`
- `M` `src/cadrumo/application/aggregation/tests/test_retenciones_aggregation_resolver.py`
- `M` `src/cadrumo/application/aggregation/tests/test_retenciones_empty_store_advisory_guard.py`
- `M` `src/cadrumo/application/aggregation/tests/test_terminal_preconditions.py`
- `M` `src/cadrumo/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`
- `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `M` `src/cadrumo/application/modelo/calculation_route.py`
- `M` `src/cadrumo/application/overview/calendar_warnings.py`
- `M` `src/cadrumo/core/external_constants.py`
- `M` `src/cadrumo/domain/calculations/registry/applicability.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py`
- `verify:` `uv run ruff check <S33 scoped paths>` -> `pass`
- `verify:` `uv run pytest -q -n 0 dev/registry/tests/test_facts_external_constants_retirement.py` -> `pass`
- `verify:` `uv run pytest -q -n 0 dev/registry/tests/test_applicability_fragment_family.py -k iva_regime_coverage` -> `pass`
- `verify:` `uv run python -m compileall -q <S33 production paths>` -> `pass`

## Notes

`uv run pytest -q -n 0 src/cadrumo/application/aggregation/tests/test_retenciones_aggregation_resolver.py -k public_retenciones_resolver` is blocked during collection because the required signed `src/cadrumo/_data/registry/authority/authority.json` is absent. No artifact was fabricated.
