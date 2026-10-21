---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-10-21'
modified: '2026-10-21'
body_schema: 'body-v2'
body_hash: 'sha256:2ab8022634fbe8f2f47851219fa8054de5f1721991b71a3fe97b99f41ca8afb9'
related:
  - "[[2026-10-21-agent-harness-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `agent-harness` ledger

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

- `S01` `verify:` `git -C Y:/code/cadrumo-agent-worktrees/main log --diff-filter=A --format=%h-%cI-%s -- src/cadrumo_agent/harness/_data/agent: fork point 5bdf185 2026-10-16T09:18:40+02:00` -> `pass`
- `S01` `verify:` `git -C Y:/code/cadrumo-worktrees/tui log --format=%h-%cI-%s e4188cc067 -- src/cadrumo_harness/_data/agent: only post-fork change is 72cd94bc66 to reference/command-operations.md` -> `pass`
- `S01` `by:` `implementation-engineer-standard`
- `S02` `D` `src/cadrumo_harness/mcp/operating_layer.py`
- `S02` `D` `src/cadrumo_harness/mcp/tests/test_operating_layer.py`
- `S02` `M` `src/cadrumo_harness/mcp/server.py`
- `S02` `M` `src/cadrumo_harness/mcp/runtime_adapter.py`
- `S02` `M` `src/cadrumo_harness/mcp/protocol_contract.py`
- `S02` `M` `src/cadrumo_harness/mcp/surfaces.py`
- `S02` `M` `src/cadrumo_harness/mcp/main.py`
- `S02` `M` `src/cadrumo_harness/mcp/tests/test_installed_stdio.py`
- `S02` `M` `src/cadrumo_harness/mcp/tests/test_tool_annotations.py`
- `S02` `M` `src/cadrumo_harness/mcp/tests/test_mcp_surface_pins.py`
- `S02` `M` `dev/quality/metadata/import_load_targets.json`
- `S02` `M` `dev/quality/metadata/import_load_targets.cadrumo_harness.json`
- `S02` `verify:` `pytest src/cadrumo_harness/mcp/tests` -> `pass`
- `S02` `verify:` `pytest -m integration src/cadrumo_harness/mcp/tests/test_installed_stdio.py test_tool_annotations.py test_mcp_surface_pins.py test_mcp_surfaces.py` -> `pass`
- `S02` `verify:` `ty check src/cadrumo_harness` -> `pass`
- `S02` `by:` `implementation-engineer-high`

## Notes

- `S01` No skill or rule semantic changes found after the cadrumo-agent fork date (2026-10-16T09:18:40+02:00); last rules/skills commit before e4188cc067 was ca427b0666 (2026-10-15), which predates the fork. The only post-fork Cadrumo commit touching `src/cadrumo_harness/_data/agent` is 72cd94bc66, editing reference/command-operations.md only; that generated operation catalogue is explicitly out of scope per the plan (cadrumo-agent derives operation knowledge from MCP discovery) and no cadrumo-agent skill references it. No port was applicable; no cadrumo-agent file was edited.
- `S01` Concurrent cadrumo-agent dirty files (rules/cadrumo-operator-operating-rules.md, skills/cadrumo-alta-contribuyente/SKILL.md, skills/cadrumo-calendario-fiscal/SKILL.md) were left untouched per instruction; no port was owed to them since no qualifying post-fork Cadrumo-side change existed.
