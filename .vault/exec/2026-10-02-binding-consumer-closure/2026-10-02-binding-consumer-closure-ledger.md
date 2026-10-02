---
tags:
  - '#exec'
  - '#binding-consumer-closure'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:827d94feac7bd46044f746df18967ca38b8aa1a877ae0366479aa14b5e5ec713'
related:
  - "[[2026-10-02-binding-consumer-closure-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `binding-consumer-closure` ledger

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

- `S01` `M` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/bindings/0001-declarations.toml`
- `S01` `M` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/form_layouts/0001-form-layout.toml`
- `S01` `M` `dev/registry/mappings/modelo_360/2010/0002-pagina01.toml`
- `S01` `M` `dev/registry/mappings/modelo_360/2010/0003-pagina02.toml`
- `S01` `M` `src/cadrumo/application/modelo/work_form.py`
- `S01` `M` `src/cadrumo/application/modelo/tests/test_work_form_binding_labels.py`
- `S01` `R` `src/cadrumo/entrypoints/tests/test_modelo_wire_input_alias.py` -> `src/cadrumo/entrypoints/tests/test_modelo_casilla_wire_slot.py`
- `S01` `verify:` `python -m dev.registry.conformance valid` -> `pass`
- `S01` `verify:` `python -m dev.registry.form_layout generate --modelo 360 --check` -> `pass`
- `S01` `verify:` `pytest test_work_form_binding_labels test_work_form_grids test_modelo_casilla_wire_slot test_row_bindings_are_consumed -m 'unit or integration' (23)` -> `pass`
- `S01` `verify:` `basedpyright, ty, pyrefly on changed modules` -> `pass`
- `S02` `A` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2026/identifier_evolutions/0001-declarations.toml`
- `S02` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2026/form_layouts/0001-form-layout.toml`
- `S02` `verify:` `python -m dev.registry.conformance valid` -> `pass`
- `S03` `D` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2022/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2022/constructs/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2022/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2022/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/revision.toml`
- `S03` `D` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/constructs/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/constructs/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-desde-09-y-3t/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-hasta-08-y-2t/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-hasta-08-y-2t/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-hasta-08-y-2t/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/constructs/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/revision.toml`
- `S03` `A` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-desde-09-y-3t/bindings/`
- `S03` `A` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/`
- `S03` `M` `dev/registry/tests/test_modelo_184_filing_surface_across_supported_years.py`
- `S03` `M` `dev/registry/tests/test_modelo_390_registry.py`
- `S03` `M` `dev/registry/tests/test_ledger_iva_aggregation_binding_exports_recargo.py`
- `S03` `M` `src/cadrumo/adapters/persistence/profile/tests/test_modelo_303_compensacion_carry_forward_continuity.py`
- `S03` `M` `dev/registry/form_layout/tests/test_form_layout_integrity.py`
- `S03` `verify:` `typed equivalence (scratch loader diff) 232/184/390/303: only intended losses plus source_refs corrected to each edition's own design` -> `pass`
- `S03` `verify:` `python -m dev.registry.conformance valid` -> `pass`
- `S03` `verify:` `affected registry, calculation and persistence tests (421)` -> `pass`
- `S04` `M` `src/cadrumo/domain/calculations/registry/schema_surfaces.py`
- `S04` `M` `src/cadrumo/domain/calculations/registry/tests/test_schema.py`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/revision.toml`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/bindings/0001-declarations.toml`
- `S04` `verify:` `pytest test_schema -k 'not_bound or input_kind'` -> `pass`

## Notes

- `S02` Committed together with S03 and S04: the 390 2026 form-layout digest covers bindings S03 relocates, so S02 alone would not be a consistent tree.
- `S03` Grounding: 390 2022/2023 designs print no 2%, 7.5%, 0.26% or 1% boxes and 2022 no 0.62% box; 303 2022 design leaves every recargo row free (rate-specific rows are a 2023 novelty per the IVA 2022 manual).
- `S03` 184 member rows leave the applicability-grade 2022 floor, reversing that floor's earlier reduccion grounding, because nothing on the floor reads them.
- `S04` Re-scoped on evidence: the 45 vinculada casillas stay informational because Modelo232VinculadaRow detail rows fill them `(revision_replay_inputs);` their duplicate manual bindings are removed instead of bound, and informative modelos refuse bound casillas.
