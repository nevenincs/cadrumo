---
tags:
  - '#exec'
  - '#period-grammar-standardisation'
date: '2026-06-11'
step_id: 'S33'
related:
  - "[[2026-06-11-period-grammar-standardisation-plan]]"
---

# DEFERRED C2: migrate CalculationSourceContext.period to core.Period plus resolver mesh

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`
- `src/aeat/application/aggregation/_modelo_bindings.py`
- `src/aeat/application/aggregation/_source_profile.py`
- `src/aeat/application/calculations/_iva_wallet_reconciliation.py`
- `src/aeat/application/calculations/_multi_year.py`
- `src/aeat/application/calculations/_relation_prefill.py`
- `src/aeat/application/invoices/_source_resolver.py`
- `src/aeat/application/modelo/_borrador_binding.py`
- `src/aeat/application/modelo/_binding_resolution.py`
- `src/aeat/application/modelo/_calculation_actions.py`
- `src/aeat/application/modelo/_iva_wallet_gate.py`
- `src/aeat/application/modelo/_taxation_comparison.py`
- 12 test files across aggregation, calculations, invoices, and modelo test directories

## Description

Migrated `CalculationSourceContext.period` from `str` to `core.Period` (typed value
object). All 4 construction sites now call `Period.from_year_and_code(year, token)`:

- `_calculation_actions.py`: from `WorkUnit.period` (bare str) + `WorkUnit.filing_year`
- `_binding_resolution.py`: two sites — from `RegistrySnapshot.period` + `snapshot.filing_year`, and from bare `period: str` + `filing_year` parameter
- `_iva_wallet_gate.py`: from bare `period: str` + `filing_year` parameter
- `_taxation_comparison.py`: from `RegistrySnapshot.period` + `snapshot.filing_year`

All 7 resolver consumer files updated: every `context.period` usage becomes
`context.period.registry_token` where downstream APIs take `str`:

- `_modelo_bindings.py`: 3 sites in `aggregation_period_for_modelo()` calls
- `_source_profile.py`: 1 site
- `_iva_wallet_reconciliation.py`: 1 site (decision.target_period comparison)
- `_multi_year.py`: 1 site
- `_relation_prefill.py`: 2 sites (authority.snapshot and materialize_relation_binding_values)
- `_borrador_binding.py`: 2 sites (authority.snapshot and Modelo100BorradorBindingCommand.period)
- `_source_resolver.py`: 1 site (_date_in_period)

Observation key shape unchanged: `observation_key(modelo, filing_year, period: str)` still
takes a bare str; callers passing `context.period` now pass `context.period.registry_token`.
Key format `{modelo}:{filing_year}:{period}` is preserved with the same registry tokens.

Import-sort fix in `_source_mesh.py`: moved `from ...core import Period` before
`from ...core._models import STRICT_FROZEN_CONFIG`.

## Outcome

- Import smoke: `python -c "import aeat.entrypoints.cli"` OK
- `uv run --no-sync ruff check` on all 12 production files: all checks passed
- `uv run --no-sync ruff check` on all 12 test files: all checks passed
- `pytest src/aeat/application/aggregation/ src/aeat/application/calculations/ -q --tb=short`: 732 passed
- `pytest src/aeat/application/invoices/ src/aeat/application/modelo/ -q --tb=no --ignore=src/aeat/application/modelo/tests/test_file_flow_pdf.py --ignore=src/aeat/application/modelo/tests/test_file_flow_xml.py`:
  - 475 passed, 7 pre-existing failures (_workflow_gate.py peer WIP — concurrent agent
    already partially migrated that file with `Period` usage but deadline domain still
    returns str; DO NOT TOUCH file), 4 pre-existing errors (fixture collection issues
    in test_local_cross_period_carry.py — isolated_runtime_profile marker requirements)
  - 0 new failures introduced by this migration
- Commit: `1e3f795ca` — `refactor(calculations): typed core.Period on CalculationSourceContext + resolver mesh + observation key (W02.P08 C2)`

## Notes

Pre-existing failures in `_workflow_gate.py`-dependent tests are caused by a concurrent
peer agent's WIP (that agent is migrating the deadline domain to return typed `Period`
objects, which `_workflow_gate.py` already expects but the deadline domain has not yet
completed). These 7 failures predate and are independent of this C2 migration.
