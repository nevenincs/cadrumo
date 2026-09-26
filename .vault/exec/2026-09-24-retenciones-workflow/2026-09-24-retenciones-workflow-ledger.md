---
tags:
  - '#exec'
  - '#retenciones-workflow'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:646ecfa76c97509b2db649bdc62393f41a89c8d3177e7a54c5052e307ec2d8c2'
related:
  - "[[2026-09-24-retenciones-workflow-plan]]"
---

# `retenciones-workflow` ledger

## Changes

- `S01` `M` `src/cadrumo/domain/calculations/registry/withholding_bindings.py`
- `S01` `A` `src/cadrumo/domain/calculations/registry/tests/test_withholding_devengo_grouping.py`
- `S01` `M` `src/cadrumo/application/calculations/row_set_assembly.py`
- `S01` `verify:` `pytest test_withholding_devengo_grouping, registry -k withholding, test_withholding_producer, test_row_set_assembly` -> `pass`
- `S02` `M` `src/cadrumo/application/aggregation/withholding_source.py`
- `S02` `M` `src/cadrumo/application/aggregation/retencion_observations_repository.py`
- `S02` `M` `src/cadrumo/adapters/persistence/profile/retencion_observations.py`
- `S02` `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `S02` `A` `src/cadrumo/application/aggregation/tests/test_withholding_source_m193_phases.py`
- `S02` `M` `src/cadrumo/locales/en/common.yml`
- `S02` `verify:` `pytest m193 phases, withholding source, retenciones resolver, empty-store guard, locale parity` -> `pass`
- `S06` `M` `src/cadrumo/application/aggregation/m193_phase_materialization.py`
- `S06` `M` `src/cadrumo/application/aggregation/withholding_source.py`
- `S06` `M` `src/cadrumo/application/aggregation/source_mesh.py`
- `S06` `M` `src/cadrumo/application/aggregation/tests/test_withholding_source_m193_phases.py`
- `S06` `verify:` `pytest m193 phases, withholding resolver, producer, ledger capital, source mesh` -> `pass`
- `S09` `M` `src/cadrumo/application/modelo/export.py`
- `S09` `M` `src/cadrumo/application/modelo/preconditions.py`
- `S09` `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `S09` `M` `src/cadrumo/application/aggregation/m193_phase_materialization.py`
- `S09` `A` `src/cadrumo/application/modelo/tests/test_m193_settled_row_export_gate.py`
- `S09` `A` `dev/quality/tests/test_capability_flags_have_production_readers.py`
- `S09` `verify:` `pytest export gate 7, application/modelo 1472, core/errors 43, capability flag guard` -> `pass`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/revision.toml`
- `S03` `M` `dev/registry/tests/test_modelo_193_registry.py`
- `S03` `verify:` `inspect_authoring_candidate publication_valid 0 findings; test_modelo_193_registry and generated export trees anchor test 43` -> `pass`

## Notes

- `S01` test_grouping_dispatch_coverage fails on per_type2_record from the Modelo 180 row bindings (b7b4e95d20), pre-existing and outside this Step
- `S02` the 123 loader reads quarterly windows only, matching capture and the 111 loader; monthly 123 filers are an existing wider gap
- `S06` end-to-end calculate assertion parked until S03 is published; filing_export_supported is read by nothing, so the export gate is a new Step
- `S09` detection uses the phase contributor plus the 2025 accrual bound because the revision does not persist the phase; exact per-row detection needs CalculationSourceRef to keep source_filing_year
- `S03` runtime adoption waits for the next authority republish; S04 byte tests run after it
