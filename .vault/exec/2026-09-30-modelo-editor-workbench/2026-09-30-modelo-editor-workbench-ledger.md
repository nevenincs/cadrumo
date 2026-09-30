---
tags:
  - '#exec'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:a2146d4b8638a25bfe6214de117808aa2ec9a487554e40349096c0e81d98694e'
related:
  - "[[2026-09-30-modelo-editor-workbench-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `modelo-editor-workbench` ledger

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

- `S15` `A` `src/cadrumo/application/modelo/value_presentation.py`
- `S15` `A` `src/cadrumo/application/modelo/tests/test_value_presentation.py`
- `S15` `M` `src/cadrumo/application/modelo/calculation_summary_presentation.py`
- `S15` `M` `src/cadrumo/application/modelo/tests/test_calculation_summary_presentation.py`
- `S15` `verify:` `pytest test_value_presentation.py test_calculation_summary_presentation.py` -> `pass`
- `S15` `verify:` `ruff check + format` -> `pass`
- `S15` `verify:` `ty + basedpyright + pyrefly on touched files` -> `pass`
- `S15` `by:` `orchestrator`
- `S16` `A` `src/cadrumo/application/modelo/source_policy.py`
- `S16` `A` `src/cadrumo/application/modelo/tests/test_source_policy.py`
- `S16` `verify:` `pytest test_source_policy.py` -> `pass`
- `S16` `verify:` `ruff + ty + basedpyright` -> `pass`
- `S16` `by:` `orchestrator`
- `S20` `M` `src/cadrumo/entrypoints/tui/components/status.py`
- `S20` `M` `src/cadrumo/entrypoints/tui/components/tests/test_widgets.py`
- `S20` `M` `src/cadrumo/entrypoints/tui/components/widgets.py`
- `S20` `M` `src/cadrumo/entrypoints/tui/modelo/view/models.py`
- `S20` `M` `src/cadrumo/locales/ca/flows.yml`
- `S20` `M` `src/cadrumo/locales/en/flows.yml`
- `S20` `M` `src/cadrumo/locales/es/flows.yml`
- `S20` `M` `src/cadrumo/locales/hu/flows.yml`
- `S20` `M` `src/cadrumo/locales/es/modelo/schema/100.yml`
- `S20` `A` `dev/tui/tests/test_shipped_glyphs_are_in_the_pinned_font.py`
- `S20` `verify:` `pytest dev/tui/tests/test_shipped_glyphs_are_in_the_pinned_font.py` -> `pass`
- `S20` `verify:` `pytest tui components + modelo view + manager onboarding + theme (79 ran)` -> `pass`
- `S20` `by:` `orchestrator`
- `S17` `A` `src/cadrumo/application/modelo/work_form.py`
- `S17` `A` `src/cadrumo/application/modelo/work_form_models.py`
- `S17` `A` `src/cadrumo/application/modelo/tests/test_work_form.py`
- `S17` `M` `src/cadrumo/locales/ca/application.yml`
- `S17` `M` `src/cadrumo/locales/en/application.yml`
- `S17` `M` `src/cadrumo/locales/es/application.yml`
- `S17` `M` `src/cadrumo/locales/hu/application.yml`
- `S17` `verify:` `pytest test_work_form.py (11, real 130 registry)` -> `pass`
- `S17` `verify:` `ruff + ty + basedpyright + pyrefly` -> `pass`
- `S17` `by:` `orchestrator`
- `S18` `A` `src/cadrumo/application/modelo/casilla_help.py`
- `S18` `A` `src/cadrumo/application/modelo/tests/test_casilla_help.py`
- `S18` `M` `src/cadrumo/locales/ca/application.yml`
- `S18` `M` `src/cadrumo/locales/en/application.yml`
- `S18` `M` `src/cadrumo/locales/es/application.yml`
- `S18` `M` `src/cadrumo/locales/hu/application.yml`
- `S18` `verify:` `pytest test_casilla_help.py (7, real 130 registry)` -> `pass`
- `S18` `verify:` `ruff + ty + basedpyright + pyrefly` -> `pass`
- `S18` `by:` `orchestrator`
- `S21` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/__init__.py`
- `S21` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/vocabulary.py`
- `S21` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py`
- `S21` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/__init__.py`
- `S21` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_casilla_list.py`
- `S21` `M` `src/cadrumo/locales/ca/common.yml`
- `S21` `M` `src/cadrumo/locales/en/common.yml`
- `S21` `M` `src/cadrumo/locales/es/common.yml`
- `S21` `M` `src/cadrumo/locales/hu/common.yml`
- `S21` `verify:` `pytest workbench tests + glyph font gate (16)` -> `pass`
- `S21` `verify:` `ruff + ty + basedpyright` -> `pass`
- `S21` `verify:` `rasterised captures at 80, 120 and 160 columns, missing glyphs none` -> `pass`
- `S21` `by:` `orchestrator`
- `S22` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py`
- `S22` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/keys.py`
- `S22` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/page_items.py`
- `S22` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/ports.py`
- `S22` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/progress.py`
- `S22` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`
- `S22` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/wording.py`
- `S22` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/workbench_fixture.py`
- `S22` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_screen.py`
- `S22` `M` `src/cadrumo/locales/ca/common.yml`
- `S22` `M` `src/cadrumo/locales/en/common.yml`
- `S22` `M` `src/cadrumo/locales/es/common.yml`
- `S22` `M` `src/cadrumo/locales/hu/common.yml`
- `S22` `verify:` `pytest workbench tests (12)` -> `pass`
- `S22` `verify:` `ruff + ty` -> `pass`
- `S22` `verify:` `rasterised captures 80x24 en, 120x36 es and hu, 160x48 es, light and dark, missing glyphs none` -> `pass`
- `S22` `by:` `orchestrator`
- `S23` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/editor.py`
- `S23` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/review.py`
- `S23` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/session.py`
- `S23` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`
- `S23` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/ports.py`
- `S23` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/workbench_fixture.py`
- `S23` `A` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_editing.py`
- `S23` `M` `src/cadrumo/locales/ca/common.yml`
- `S23` `M` `src/cadrumo/locales/en/common.yml`
- `S23` `M` `src/cadrumo/locales/es/common.yml`
- `S23` `M` `src/cadrumo/locales/hu/common.yml`
- `S23` `verify:` `pytest workbench tests (20)` -> `pass`
- `S23` `verify:` `ruff + ty` -> `pass`
- `S23` `verify:` `rasterised editor and review captures at 80x24 and 120x36` -> `pass`
- `S23` `by:` `orchestrator`

## Notes

- `S20` 6 TUI tests errored at import on a concurrent session's uncommitted launcher.py edit (ModeloWorkspaceReadContendedError without an error-code entry); not caused by this Step
- `S17` Builder consumes the declared layout types merged from the layout-family lane; integration over every published layout waits for that lane's generator
- `S22` Screen reads through a port the composition root will supply; production wiring lands with the page retirement Step
- `S23` The parse, apply and lifecycle actions arrive through a port; the production adapter onto the edit contract's parser and door lands with the page retirement Step once the edit-correctness lane merges
- `S23` Result diff after apply deferred to acceptance phase
