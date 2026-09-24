---
tags:
  - '#exec'
  - '#retenciones-workflow'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:552f7441cc4b60e83fc47817feb847e7f73ed1751b1deefb5ef9e193270de928'
related:
  - "[[2026-09-24-retenciones-workflow-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `retenciones-workflow` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->
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

