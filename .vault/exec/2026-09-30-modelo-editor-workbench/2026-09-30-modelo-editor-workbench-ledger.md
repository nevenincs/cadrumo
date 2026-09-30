---
tags:
  - '#exec'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:f20219894038764381ba19aaba8f6a848228536267f7058372dff8d577666f4a'
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

## Notes

- `S20` 6 TUI tests errored at import on a concurrent session's uncommitted launcher.py edit (ModeloWorkspaceReadContendedError without an error-code entry); not caused by this Step
- `S17` Builder consumes the declared layout types merged from the layout-family lane; integration over every published layout waits for that lane's generator
