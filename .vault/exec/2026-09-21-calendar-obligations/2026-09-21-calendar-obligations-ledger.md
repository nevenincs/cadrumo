---
tags:
  - '#exec'
  - '#calendar-obligations'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:841ff81249a8ee0267195a9c8e563de435b6ab9c86bd35d6de386df99ea47b43'
related:
  - "[[2026-09-21-calendar-obligations-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `calendar-obligations` ledger

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
- `S01` `M` `src/cadrumo/domain/deadlines/engine.py`
- `S01` `M` `src/cadrumo/application/overview/calendar_models.py`
- `S01` `M` `src/cadrumo/application/overview/calendar.py`
- `S01` `M` `src/cadrumo/application/overview/tests/test_calendar.py`
- `S01` `M` `src/cadrumo/application/overview/tests/test_home.py`
- `S01` `M` `src/cadrumo/application/overview/tests/test_calendar_filing_evidence.py`
- `S01` `M` `src/cadrumo/application/modelo/tests/test_declarations_calendar.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/workbench_fixtures.py`
- `S01` `A` `.vault/plan/2026-09-21-calendar-obligations-plan.md`
- `S01` `A` `.vault/index/calendar-obligations.index.md`
- `S01` `verify:` `uv run ty check calendar deadline files` -> `pass`
- `S02` `M` `src/cadrumo/application/overview/calendar.py`
- `S02` `M` `src/cadrumo/application/overview/tests/test_calendar.py`
- `S02` `M` `.vault/plan/2026-09-21-calendar-obligations-plan.md`
- `S02` `M` `.vault/index/calendar-obligations.index.md`
- `S02` `verify:` `uv run ty check calendar.py` -> `pass`
- `S02` `verify:` `uv run pytest -n 0 test_calendar.py` -> `pass`
- `S02` `verify:` `uv run ruff check calendar files` -> `pass`
- `S03` `M` `src/cadrumo/domain/deadlines/engine.py`
- `S03` `M` `src/cadrumo/domain/deadlines/tests/test_activity_window_gate.py`
- `S03` `M` `.vault/plan/2026-09-21-calendar-obligations-plan.md`
- `S03` `M` `.vault/index/calendar-obligations.index.md`
- `S03` `verify:` `uv run pytest -n 0 deadline engine lifecycle tests` -> `pass`
- `S03` `verify:` `uv run ruff check deadline lifecycle files` -> `pass`
- `S03` `verify:` `uv run ty check deadline engine` -> `pass`

