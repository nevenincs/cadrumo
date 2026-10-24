---
tags:
  - '#exec'
  - '#desktop-modelo-workspace'
date: '2026-10-23'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:2c99ba5c811ef34e4c643ff16ce0fb2524170a6f09bf64d5a82eb8d0d21f6d86'
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
- `S03` `A` `src/cadrumo/application/modelo/work_form_wording.py`
- `S03` `M` `dev/locales/fstring_registry.py`
- `S03` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_work_form_filer_attention.py`
- `S03` `M` `src/cadrumo/application/modelo/work_form.py`
- `S03` `M` `src/cadrumo/application/modelo/work_form_layout.py`
- `S03` `M` `src/cadrumo/application/modelo/work_form_models.py`
- `S03` `M` `src/cadrumo/application/modelo/workbench_projection.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/declarations/controller.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/declarations/picker.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/declarations/portfolio_rows.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/declarations/row_words.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list_models.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list_values.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/editor.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/editor_explanations.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/header.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/page_items.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/progress.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/review.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_editor.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_help_content.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_navigation.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_operation.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/sources.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_casilla_editor_panel.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_casilla_list.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_casilla_row_anatomy.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_held_values_and_sources.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_rate_boxes_real.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_bulk_confirm_real.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_confirm_real.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_deadline_parity.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_export_state.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_header.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_marks.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_origin_in_help.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_progress.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_refinements_real.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_review_check.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/vocabulary.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/wording.py`
- `S03` `verify:` `pytest -n0 TUI modelo workbench + declarations suites (383 + 513)` -> `pass`
- `S03` `verify:` `pytest -n0 application form, loading, projection, every-revision, manifest (78)` -> `pass`
- `S03` `verify:` `ruff, format, lint-imports (30 kept), dev.quality.types (0), operation contract manifest regenerated` -> `pass`
- `S03` `verify:` `dev.locales status: no moved key family became catalogue-only` -> `pass`
- `S04` `M` `src/cadrumo/application/modelo/work_form_wording.py`
- `S04` `M` `src/cadrumo/application/modelo/work_form_models.py`
- `S04` `M` `src/cadrumo/application/modelo/workbench_projection.py`
- `S04` `M` `src/cadrumo/application/modelo/tests/test_work_form_filer_attention.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list_values.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list_layout.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/page_items.py`
- `S04` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S04` `verify:` `pytest work_form_filer_attention, TUI casilla_list/grid/rate/held/formula, workbench operations and form loading` -> `pass`
- `S04` `verify:` `dev.quality.types --count` -> `pass`
- `S04` `verify:` `lint-imports` -> `pass`
- `S04` `verify:` `operation_contract_manifest.generate --check` -> `pass`

## Notes

- `S02` Fixes an S01 defect: a design-constant cell kept the standing of its pre-copy origin; field copies that change state now go through `revised_field`
- `S03` Also moved period and date wording from the TUI (needed by origin words); the frontend-neutral key namespace remains P02
