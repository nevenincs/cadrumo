---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:7be25800521872e557ddf0f63a3dada81e48a40c82f4c19aba6b78754be883a6'
step_id: 'S378'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Build the full declaration calendar as an agenda-first searchable and filterable workbench with past, upcoming, overdue, filed, and evidence-unknown scopes

## Scope

- `src/cadrumo/entrypoints/tui/declarations/calendar.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/declarations/calendar.py`
- `M` `src/cadrumo/entrypoints/tui/declarations/controller.py`
- `M` `src/cadrumo/entrypoints/tui/declarations/models.py`
- `M` `src/cadrumo/entrypoints/tui/declarations/routes.py`
- `A` `src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py`
- `M` `src/cadrumo/entrypoints/tui/declarations/tests/test_declarations_workspace.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `M` `.vault/exec/2026-08-11-tui-architecture/2026-08-11-tui-architecture-W08-P27-S378.md`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/tui/declarations/calendar.py src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/tui/declarations/calendar.py src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright src/cadrumo/entrypoints/tui/declarations/calendar.py src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py` -> `pass`
- `verify:` `npx --yes jscpd@4.2.0 src/cadrumo/entrypoints/tui/declarations/calendar.py src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py --format python --min-lines 6 --min-tokens 80 --max-size 250kb --reporters console --noTips` -> `pass`
<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->
