---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:3b8af879b4a7b484da41a5646c3ac1b14dd305824aa5c638c4de63380654bc0a'
step_id: 'S20'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Make terminal-origin expectations auditable: default the expectation to the registration's permitted origin classes when a row authors none, compare the resolved provenance origin class against it at resolution, and surface a mismatch as a structured diagnostic; route the unreferenced-binding advisory into the registry status report

## Scope

- `src/cadrumo/application/aggregation/source_resolution_operations.py`
- `src/cadrumo/application/aggregation/source_mesh.py`
- `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `dev/registry/compiler/validate_bindings.py`
- `dev/registry/analysis/`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/binding_terminal_audit.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_binding_terminal_audit.py`
- `A` `src/cadrumo/application/aggregation/terminal_origin_audit.py`
- `A` `src/cadrumo/application/aggregation/tests/test_terminal_origin_audit.py`
- `M` `src/cadrumo/application/aggregation/source_mesh.py`
- `M` `src/cadrumo/application/aggregation/atribucion_member.py`
- `M` `src/cadrumo/application/aggregation/foreign_assets.py`
- `M` `src/cadrumo/application/aggregation/modelo_bindings.py`
- `M` `src/cadrumo/application/aggregation/modelo_bindings_renta_expenses.py`
- `M` `src/cadrumo/application/aggregation/modelo_bindings_retenciones.py`
- `M` `src/cadrumo/application/aggregation/oss_ioss.py`
- `M` `src/cadrumo/application/aggregation/withholding_source.py`
- `M` `src/cadrumo/application/invoices/source_resolver.py`
- `M` `src/cadrumo/application/calculations/bienes_inversion_regularizacion.py`
- `M` `src/cadrumo/application/calculations/iva_compensation_annual_partition.py`
- `M` `src/cadrumo/application/calculations/iva_wallet_reconciliation.py`
- `M` `src/cadrumo/application/calculations/m303_regimen_simplificado_annual_summary.py`
- `M` `src/cadrumo/application/calculations/multi_year.py`
- `M` `src/cadrumo/application/calculations/prorrata_regularizacion.py`
- `M` `src/cadrumo/application/calculations/tests/test_previous_filing_unsatisfied_diagnostic.py`
- `M` `src/cadrumo/application/modelo/borrador_binding.py`
- `M` `src/cadrumo/application/modelo/profile_binding.py`
- `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `M` `src/cadrumo/application/modelo/_calculation_source_staging.py`
- `M` `src/cadrumo/application/modelo/tests/test_profile_binding.py`
- `M` `dev/registry/analysis/registry_status.py`
- `M` `dev/registry/tests/test_schema_hygiene.py`
- `verify:` `uv run ruff check <touched files>` -> `pass`
- `verify:` `uv run ty check <touched files>` -> `pass`
- `verify:` `uv run basedpyright <new files>` -> `pass`
- `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_binding_terminal_audit.py src/cadrumo/application/aggregation/tests/test_terminal_origin_audit.py -n 0` -> `fail`

## Notes

The two new suites (46 cases) pass when their test functions are executed
directly; under pytest they error in the session-scoped `compose_runtime_ports`
fixture, because the bundled authority artifact in this worktree no longer
decodes against the live `RelationPrefillProvider` model while a concurrent
relation-absorption change is mid-republish. The failure is environmental and
affects every suite in the repository, not only these.

Two resolver-level assertions (profile resolver, previous-filing resolver) were
added to existing suites but could not be executed for the same reason.

`src/cadrumo/application/calculations/relation_prefill.py` is owned by the
concurrent change and was left untouched, so its provenance rows still carry no
terminal origin.
