---
tags:
  - '#exec'
  - '#export-parity'
date: '2026-11-01'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:cb3588e58b84147d6f65b1680e75f391235bcced905b6c4706397aa4ea1eb27f'
related:
  - "[[2026-11-01-export-parity-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `export-parity` ledger

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

- `S14` `M` `dev/locales/fstring_registry.py`
- `S14` `M` `dev/locales/tests/test_audit.py`
- `S14` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S14` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S14` `M` `dev/quality/metadata/import_load_targets.json`
- `S14` `M` `dev/registry/binding_signal/semantics.py`
- `S14` `M` `dev/registry/compiler/_validate_revision_sections.py`
- `S14` `A` `dev/registry/compiler/tests/test_binding_grade_cap_validation.py`
- `S14` `A` `dev/registry/compiler/validate_binding_grade_caps.py`
- `S14` `M` `src/cadrumo/_data/registry/aeat/legal/irpf.toml`
- `S14` `M` `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0001-declarations.toml`
- `S14` `M` `src/cadrumo/application/aggregation/modelo_bindings.py`
- `S14` `M` `src/cadrumo/application/aggregation/source_diagnostic_reason.py`
- `S14` `M` `src/cadrumo/application/aggregation/source_mesh.py`
- `S14` `M` `src/cadrumo/application/aggregation/source_resolution_operations.py`
- `S14` `M` `src/cadrumo/application/aggregation/tests/test_renta_income_actividad_contract.py`
- `S14` `A` `src/cadrumo/application/modelo/advisory_binding_value.py`
- `S14` `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `S14` `M` `src/cadrumo/application/modelo/calculation_advisory_projection.py`
- `S14` `M` `src/cadrumo/application/modelo/calculation_bucket_actions.py`
- `S14` `M` `src/cadrumo/application/modelo/calculation_note_gate.py`
- `S14` `M` `src/cadrumo/application/modelo/calculation_notes.py`
- `S14` `A` `src/cadrumo/application/modelo/calculation_screen.py`
- `S14` `M` `src/cadrumo/application/modelo/calculation_source_mesh_actions.py`
- `S14` `M` `src/cadrumo/application/modelo/revision_persistence.py`
- `S14` `A` `src/cadrumo/application/modelo/tests/test_advisory_binding_value_gate.py`
- `S14` `M` `src/cadrumo/application/modelo/tests/test_asset_notes_on_the_record.py`
- `S14` `M` `src/cadrumo/application/modelo/tests/test_calculation_note_wording.py`
- `S14` `M` `src/cadrumo/application/modelo/tests/test_work_form_gate_agreement.py`
- `S14` `M` `src/cadrumo/application/modelo/work_form.py`
- `S14` `M` `src/cadrumo/application/modelo/work_form_notes.py`
- `S14` `M` `src/cadrumo/core/aggregation.py`
- `S14` `M` `src/cadrumo/core/authority_grade.py`
- `S14` `A` `src/cadrumo/domain/calculations/registry/binding_grade_cap.py`
- `S14` `A` `src/cadrumo/domain/calculations/registry/binding_grade_cap_reach.py`
- `S14` `M` `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `S14` `M` `src/cadrumo/domain/calculations/registry/ledger_renta_income_bindings.py`
- `S14` `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `S14` `M` `src/cadrumo/domain/calculations/registry/snapshot_references.py`
- `S14` `M` `src/cadrumo/domain/modelos/calculation_revision.py`
- `S14` `M` `src/cadrumo/domain/modelos/calculation_revision_identity.py`
- `S14` `M` `src/cadrumo/domain/modelos/calculation_revision_sources.py`
- `S14` `A` `src/cadrumo/domain/modelos/calculation_screen_stamp.py`
- `S14` `M` `src/cadrumo/domain/renta/retenciones_routing_integrity.py`
- `S14` `M` `src/cadrumo/entrypoints/cli/_modelo_rendering.py`
- `S14` `M` `src/cadrumo/locales/ca/application.yml`
- `S14` `M` `src/cadrumo/locales/ca/common.yml`
- `S14` `M` `src/cadrumo/locales/en/application.yml`
- `S14` `M` `src/cadrumo/locales/en/common.yml`
- `S14` `M` `src/cadrumo/locales/es/application.yml`
- `S14` `M` `src/cadrumo/locales/es/common.yml`
- `S14` `M` `src/cadrumo/locales/hu/application.yml`
- `S14` `M` `src/cadrumo/locales/hu/common.yml`
- `S14` `verify:` `focused pytest (17 files, 586 tests)` -> `pass`
- `S14` `verify:` `just check-style` -> `pass`
- `S14` `verify:` `just check-format` -> `pass`
- `S14` `verify:` `just check-types` -> `pass`
- `S14` `verify:` `lint-imports --config .importlinter --no-cache` -> `pass`
- `S14` `verify:` `python -m dev.registry.conformance valid` -> `pass`
- `S14` `verify:` `just check-bindings` -> `pass`
- `S14` `by:` `implementation-engineer-high`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/form_layouts/0001-form-layout.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/revision.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/form_layouts/0001-form-layout.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/form_layouts/0001-form-layout.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/form_layouts/0001-form-layout.toml`
- `S05` `A` `src/cadrumo/application/aggregation/tests/test_modelo_100_actividad_retencion_credit.py`
- `S05` `verify:` `pytest focused 0599 binding, advisory gate, registry binding tests (143)` -> `pass`
- `S05` `verify:` `just check-style` -> `pass`
- `S05` `verify:` `just check-format` -> `pass`
- `S05` `verify:` `just check-types` -> `pass`
- `S05` `verify:` `lint-imports` -> `pass`
- `S05` `verify:` `dev.registry.conformance valid` -> `pass`
- `S05` `verify:` `just check-bindings` -> `pass`
- `S05` `by:` `implementer`

## Notes

- `S14` just check-import-boundaries exited 7: subordinate checker wrote no checker.json; 30/30 contracts kept and 5337/5337 modules loaded; lint-imports substitute used
- `S14` proven-zero `advisory_binding_value` diagnostics are held in-process with the calculation response and are not persisted
