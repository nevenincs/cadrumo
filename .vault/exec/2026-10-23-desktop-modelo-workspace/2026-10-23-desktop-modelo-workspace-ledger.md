---
tags:
  - '#exec'
  - '#desktop-modelo-workspace'
date: '2026-10-23'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:270faf332ef6505b1c89c77d58b39ebf4284e2718dc75fc71a1dbed88eb406c8'
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
- `S05` `A` `src/cadrumo/application/modelo/work_form_next_step.py`
- `S05` `A` `src/cadrumo/application/modelo/tests/test_work_form_next_step.py`
- `S05` `A` `src/cadrumo/application/modelo/tests/work_form_fixture.py`
- `S05` `M` `dev/locales/fstring_registry.py`
- `S05` `M` `dev/tui/harness/sequences.py`
- `S05` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S05` `M` `src/cadrumo/application/modelo/tests/test_work_form_filer_attention.py`
- `S05` `M` `src/cadrumo/application/modelo/workbench_projection.py`
- `S05` `M` `src/cadrumo/application/modelo/workbench_read.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/header.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/issue_scale.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/navigator.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/progress.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_constants.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_help_content.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_next_step.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_operation.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_presentation.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_applicability.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_apply_prerequisite.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_check_route_real.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_filing_gates.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_finding_words.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_formula_values_real.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_missing_count.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_progress.py`
- `S05` `verify:` `pytest TUI modelo workbench suite, application next-step/filer-attention/field-rules, workbench operations and form loading (779)` -> `pass`
- `S05` `verify:` `dev.quality.types --count` -> `pass`
- `S05` `verify:` `lint-imports` -> `pass`
- `S05` `verify:` `operation_contract_manifest.generate` -> `pass`
- `S06` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S06` `M` `src/cadrumo/application/modelo/tests/test_work_form_filer_attention.py`
- `S06` `M` `src/cadrumo/application/modelo/work_form_models.py`
- `S06` `M` `src/cadrumo/application/modelo/work_form_wording.py`
- `S06` `M` `src/cadrumo/application/modelo/workbench_projection.py`
- `S06` `M` `src/cadrumo/entrypoints/tui/declarations/picker.py`
- `S06` `M` `src/cadrumo/entrypoints/tui/declarations/portfolio_rows.py`
- `S06` `M` `src/cadrumo/entrypoints/tui/declarations/row_words.py`
- `S06` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/header.py`
- `S06` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/sources.py`
- `S06` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_header.py`
- `S06` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/wording.py`
- `S06` `verify:` `pytest form identity words (en/es), declarations TUI tests and workbench header (229), filer attention, workbench operations` -> `pass`
- `S06` `verify:` `dev.quality.types --count` -> `pass`
- `S06` `verify:` `lint-imports` -> `pass`
- `S06` `verify:` `operation_contract_manifest.generate` -> `pass`
- `S07` `A` `src/cadrumo/application/modelo/declarations_list_operation.py`
- `S07` `A` `src/cadrumo/application/modelo/tests/test_declarations_list_operation.py`
- `S07` `M` `src/cadrumo/application/modelo/declarations_list.py`
- `S07` `M` `src/cadrumo/application/modelo/tests/test_declarations_list.py`
- `S07` `M` `src/cadrumo/application/workbench_generation_reader.py`
- `S07` `M` `src/cadrumo/entrypoints/workbench_generation_composition.py`
- `S07` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S07` `M` `src/cadrumo/application/operations/access_facts.py`
- `S07` `M` `src/cadrumo/entrypoints/cli/command_operation_table.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/registered_executor_conformance_expectations.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/registered_executor_payload_support.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/declarations/row_words.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/declarations/portfolio_rendering.py`
- `S07` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S07` `verify:` `pytest declarations list and list operation, TUI declarations (189), registered executor conformance case and completeness, access facts, MCP surfaces, operation contract manifest tests (136), no-AEAT-write gate` -> `pass`
- `S07` `verify:` `dev.quality.types --count` -> `pass`
- `S07` `verify:` `lint-imports` -> `pass`
- `S07` `verify:` `operation_contract_manifest.generate --check` -> `pass`
- `S08` `A` `src/cadrumo/application/modelo/work_form_source_groups.py`
- `S08` `A` `src/cadrumo/application/modelo/tests/test_work_form_source_groups.py`
- `S08` `M` `src/cadrumo/application/modelo/work_form.py`
- `S08` `M` `src/cadrumo/application/modelo/work_form_models.py`
- `S08` `M` `src/cadrumo/application/modelo/workbench_projection.py`
- `S08` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/sources.py`
- `S08` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_next_step.py`
- `S08` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_held_values_and_sources.py`
- `S08` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_sources.py`
- `S08` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_sources_real.py`
- `S08` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S08` `verify:` `pytest source groups, TUI sources and real sources, check route, progress, responsive surfaces, form tests, workbench operations and loading (166)` -> `pass`
- `S08` `verify:` `lint-imports` -> `pass`
- `S08` `verify:` `operation_contract_manifest.generate` -> `pass`
- `S09` `A` `src/cadrumo/application/modelo/tests/test_casilla_help_outside_figures.py`
- `S09` `M` `src/cadrumo/application/modelo/casilla_help.py`
- `S09` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S09` `verify:` `pytest casilla help, formula values, outside figures, workbench operations (39), TUI help, footer, freshness, affects text, installed factory (67)` -> `pass`
- `S09` `verify:` `basedpyright casilla_help` -> `pass`
- `S09` `verify:` `operation_contract_manifest.generate` -> `pass`
- `S10` `M` `src/cadrumo/application/modelo/edit_models.py`
- `S10` `M` `src/cadrumo/application/modelo/edit_parsing.py`
- `S10` `M` `src/cadrumo/application/modelo/edit_apply_contracts.py`
- `S10` `M` `src/cadrumo/application/modelo/edit_apply_scalar_contracts.py`
- `S10` `M` `src/cadrumo/application/modelo/edit_operator_input.py`
- `S10` `M` `src/cadrumo/application/modelo/workbench_operations.py`
- `S10` `M` `src/cadrumo/application/modelo/tests/test_edit_parsing.py`
- `S10` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/editor.py`
- `S10` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/factory.py`
- `S10` `M` `src/cadrumo/entrypoints/tests/test_modelo_workbench_operations.py`
- `S10` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S10` `verify:` `pytest application edit tests (154), TUI editing (161), edit conformance (4), workbench operations incl. typed preflight and apply refusal, native submission stream (3), operation contract manifest tests (136)` -> `pass`
- `S10` `verify:` `basedpyright edit modules` -> `pass`
- `S10` `verify:` `operation_contract_manifest.generate` -> `pass`
- `S13` `M` `src/cadrumo_runtime/host/session_hold_operations.py`
- `S13` `M` `src/cadrumo_runtime/host/tests/test_session_hold_operations.py`
- `S13` `M` `src/cadrumo_runtime/host/tests/test_submission_stream_native.py`
- `S13` `verify:` `pytest held relay, bridge and product-neutral gate (27), native submission stream incl. no-operand refusal (3)` -> `pass`
- `S13` `verify:` `ty session_hold_operations` -> `pass`
- `S13` `M` `native/application/src/person_operations.rs`
- `S13` `M` `native/desktop/src-tauri/src/agent/person.rs`
- `S13` `verify:` `ctest application.rust (74)` -> `pass`
- `S13` `verify:` `desktop-host-unit-test (502)` -> `pass`
- `S13` `verify:` `desktop-host-unit-clippy` -> `pass`
- `S11` `M` `src/cadrumo/locales`
- `S11` `M` `dev/locales/fstring_registry.py`
- `S11` `M` `dev/locales/_ast_key_policy.py`
- `S11` `verify:` `TUI declarations, header, progress, sources, filing gates, casilla list, live language refresh (291)` -> `pass`
- `S11` `verify:` `dev/locales test_dynamic_prefix_registry_coverage (32)` -> `pass`
- `S14` `M` `.vault/plan/2026-10-23-desktop-modelo-workspace-plan.md`
- `S30` `A` `src/cadrumo/application/modelo/work_form_header.py`
- `S30` `A` `src/cadrumo/application/modelo/tests/test_work_form_header.py`
- `S30` `M` `src/cadrumo/application/modelo/workbench_read.py`
- `S30` `M` `src/cadrumo/application/modelo/workbench_projection.py`
- `S30` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/header.py`
- `S30` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_constants.py`
- `S30` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_footer.py`
- `S30` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_operation.py`
- `S30` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_applicability.py`
- `S30` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_header.py`
- `S30` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_issues.py`
- `S30` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_marks.py`
- `S30` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_missing_count.py`
- `S30` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S30` `verify:` `ruff check and format` -> `pass`
- `S30` `verify:` `lint-imports` -> `pass`
- `S30` `verify:` `basedpyright touched files` -> `pass`
- `S30` `verify:` `operation_contract_manifest --check` -> `pass`
- `S30` `verify:` `pytest test_work_form_header.py` -> `pass`
- `S30` `verify:` `pytest TUI header suites` -> `pass`
- `S30` `by:` `opus-p01-lane`
- `S34` `A` `src/cadrumo/application/modelo/work_form_issue_lines.py`
- `S34` `A` `src/cadrumo/application/modelo/tests/test_work_form_issue_lines.py`
- `S34` `M` `src/cadrumo/application/modelo/workbench_read.py`
- `S34` `M` `src/cadrumo/application/modelo/workbench_projection.py`
- `S34` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/issue_projection.py`
- `S34` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/issue_scale.py`
- `S34` `verify:` `ruff check and format` -> `pass`
- `S34` `verify:` `lint-imports` -> `pass`
- `S34` `verify:` `basedpyright touched files` -> `pass`
- `S34` `verify:` `pytest issue lines and header` -> `pass`
- `S34` `verify:` `pytest TUI issue suites` -> `pass`
- `S34` `by:` `opus-p01-lane-2`

## Notes

- `S02` Fixes an S01 defect: a design-constant cell kept the standing of its pre-copy origin; field copies that change state now go through `revised_field`
- `S03` Also moved period and date wording from the TUI (needed by origin words); the frontend-neutral key namespace remains P02
- `S05` Scope corrected from `work_form.py` to the new defining module `work_form_next_step.py;` TUI counters and ladder moved there with every consumer repointed
- `S06` Period words already moved in S03; this step moved modelo titles and put title, number and period words on the form. The list projection that uses them is S07
- `S07` The list read captures through the generation's own door with a list-only method, so the runtime gains no special case; row words and steps moved from the TUI `row_words`
- `S08` Scope corrected from `source_policy.py` to the new defining module `work_form_source_groups.py.` Type gate clean for these files; remaining findings are in another session's statement-reading files
- `S09` Citation text already reached the card's legal basis; this step proves it and adds the off-form figures. lint-imports shows one broken contract from another session's `cadrumo/tests/statement_reader_fixtures.py,` not from this step
- `S10` The native disconnect/session-lock test failed once under concurrent load and passed on rerun with all three native tests; lint-imports' one broken contract is another session's `cadrumo/tests/statement_reader_fixtures.py`
- `S13` The relay names no definition: it forwards `operation_financial_submit` as the runtime's financial input and the runtime refuses any definition whose contract takes no financial operand, so the product-neutral bridge gate still holds. Python strings cannot be zeroed; the relay drops its references to the input after transfer
- `S13` The desktop's person session now relays in Rust (another session's 4e256a9e95/8821a09cfe); the same `operation_financial_submit` action is added there, with the encoded input and its request zeroized after sending
- `S11` First part of S11: `tui.modelo.workbench.*` and `tui.declarations.*` moved to `workspace.modelo.*` and `workspace.declarations.*` through dev.locales move (469 and 201 keys per locale, values unchanged) and 3734 code references repointed in 111 files. `test_audit` still reports catalogue keys with no code reference `(next.check_aeat,` `next.link_aeat,` state.correction) and a missing provenance.source, all unreferenced before this step. The missing list and refusal keys and the key-hint removal follow
- `S14` Not implemented: the desktop's person session now relays in Rust and another session lifted the person reply bound to the relay's 16 MiB assembled-document bound in 931da66b20, which carries a 390-sized form read in one reply; the bounded-parts mechanism is unnecessary
- `S34` `contract_manifest.json` left out: the working tree also carries S31, S37 and S38 schema changes; it is regenerated and committed once those steps land
