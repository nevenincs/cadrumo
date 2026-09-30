---
tags:
  - '#exec'
  - '#tui-registry-api-gate'
date: '2026-09-23'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:353e5da3eb9004314219630452d70acb014a8c3188802e25d599c363d8a85b6f'
related:
  - "[[2026-09-23-tui-registry-api-gate-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `tui-registry-api-gate` ledger

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

- `S01` `M` `src/cadrumo/application/modelo/work_review.py`
- `S01` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_work_review.py`
- `S01` `verify:` `pytest-work-review` -> `pass`
- `S01` `verify:` `ruff` -> `pass`
- `S01` `verify:` `ty` -> `pass`
- `S03` `M` `src/cadrumo/application/modelo/workspace_producers.py`
- `S03` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_work_review.py`
- `S03` `verify:` `pytest-work-review` -> `pass`
- `S03` `verify:` `pytest-workspace-producers` -> `pass`
- `S03` `verify:` `ruff` -> `pass`
- `S03` `verify:` `ty` -> `pass`
- `S04` `M` `src/cadrumo/application/modelo/workspace.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `S04` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_work_review.py`
- `S04` `verify:` `pytest-work-review` -> `pass`
- `S04` `verify:` `pytest-tui-modelo-and-workbench` -> `pass`
- `S04` `verify:` `pytest-modelo-workspace` -> `pass`
- `S04` `verify:` `ruff` -> `pass`
- `S04` `verify:` `ty` -> `pass`
- `S05` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_workspace_destinations.py`
- `S05` `verify:` `pytest-projection-reader` -> `pass`
- `S05` `verify:` `pytest-installed-workspace` -> `pass`
- `S05` `verify:` `pytest-destinations-neighbour-refusal` -> `pass`
- `S07` `M` `src/cadrumo/domain/modelos/calculation_revision.py`
- `S07` `M` `src/cadrumo/application/modelo/calculation_resolution.py`
- `S07` `M` `src/cadrumo/application/modelo/_work_review_assembly.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_work_review.py`
- `S07` `verify:` `pytest-work-review` -> `pass`
- `S07` `verify:` `pytest-calculation-replay-and-boolean-channel` -> `pass`
- `S07` `verify:` `harness-modelo-100-scenario` -> `pass`
- `S07` `verify:` `ruff` -> `pass`
- `S07` `verify:` `ty` -> `pass`
- `S02` `M` `src/cadrumo/adapters/persistence/profile/tests/test_workspace.py`
- `S02` `M` `src/cadrumo/application/modelo/calculation.py`
- `S02` `M` `src/cadrumo/application/modelo/work_addressing.py`
- `S02` `M` `src/cadrumo/application/modelo/workspace.py`
- `S02` `M` `src/cadrumo/application/modelo/workspace_manifest.py`
- `S02` `M` `src/cadrumo/application/modelo/workspace_producers.py`
- `S02` `M` `src/cadrumo/application/state_projection.py`
- `S02` `M` `src/cadrumo/application/tests/test_workbench_generation.py`
- `S02` `M` `src/cadrumo/core/i18n/locale_catalogue.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_export_result_lifecycle.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_modelo_projection_reader.py`
- `S02` `verify:` `pytest-workspace-admission-module` -> `pass`
- `S02` `verify:` `pytest-s02-wide-1952` -> `pass`
- `S02` `verify:` `ruff` -> `pass`
- `S02` `verify:` `ty-linux-win32` -> `pass`

## Notes

- `S02` Wide run: one failure, `test_exception_base_hygiene,` names exception classes in `value_presentation.py,` `source_policy.py` and `work_form.py,` which a concurrent session committed or holds untracked; not touched here. The schema-record determinism test in `test_workspace.py` failed once in a full-module run and passed in nine subsequent runs.
