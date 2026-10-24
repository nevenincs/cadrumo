---
tags:
  - '#exec'
  - '#desktop-modelo-workspace'
date: '2026-10-23'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:4753ba756c1e39cc54ce610eed4b41cce7b3bc052217937199b3dece03c38479'
related:
  - "[[2026-10-23-desktop-modelo-workspace-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `desktop-modelo-workspace` ledger

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

- `S01` `M` `src/cadrumo/application/modelo/work_form_models.py`
- `S01` `M` `src/cadrumo/application/modelo/work_form_field_projection.py`
- `S01` `M` `src/cadrumo/application/modelo/work_form_layout.py`
- `S01` `M` `src/cadrumo/application/modelo/workbench_projection.py`
- `S01` `M` `src/cadrumo/application/modelo/tests/test_work_form_filer_attention.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/vocabulary.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list_models.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/page_items.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_grid_tables_real.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_marks.py`
- `S01` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S01` `verify:` `pytest -n0 test_work_form_filer_attention, test_workbench_marks, test_grid_tables_real (49)` -> `pass`
- `S01` `verify:` `pytest -n0 workbench_operations, work_form_loading, contract_manifest, work_form, work_form_grids (44)` -> `pass`
- `S01` `verify:` `mutation: page correction disabled fails test_a_page_that_does_not_apply_asks_for_no_value` -> `pass`
- `S01` `verify:` `ruff check+format, lint-imports (30 kept), dev.quality.types (0)` -> `pass`
- `S01` `verify:` `operation contract manifest regenerated; only modelo.work.form result schema changed` -> `pass`
- `S02` `M` `src/cadrumo/application/modelo/work_form_models.py`
- `S02` `M` `src/cadrumo/application/modelo/work_form_layout.py`
- `S02` `M` `src/cadrumo/application/modelo/work_form_inspection.py`
- `S02` `M` `src/cadrumo/application/modelo/workbench_projection.py`
- `S02` `A` `src/cadrumo/application/modelo/tests/test_work_form_field_rules.py`
- `S02` `M` `src/cadrumo/application/modelo/tests/test_work_form_filer_attention.py`
- `S02` `M` `src/cadrumo/entrypoints/tests/test_modelo_work_form_loading.py`
- `S02` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S02` `verify:` `pytest -n0 field_rules, filer_attention, work_form, work_form_grids, every_revision, contract_manifest (84)` -> `pass`
- `S02` `verify:` `pytest -n0 work_form_loading, workbench_operations (14)` -> `pass`
- `S02` `verify:` `pytest -n0 TUI review_effect, confirmation, scoped_confirm, bulk_confirm_real, confirm_real (35)` -> `pass`
- `S02` `verify:` `mutation: design-constant standing correction removed fails its regression test` -> `pass`
- `S02` `verify:` `ruff, format, lint-imports (30 kept), dev.quality.types (0), contract manifest check` -> `pass`

## Notes

- `S02` Fixes an S01 defect: a design-constant cell kept the standing of its pre-copy origin; field copies that change state now go through `revised_field`
