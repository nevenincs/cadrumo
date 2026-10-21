---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-10-21'
modified: '2026-10-21'
body_schema: 'body-v2'
body_hash: 'sha256:ed9b8c0eae9828c4a4ba64e299615a82c8b34373fc041d32a94920f103aff485'
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
- `S03` `D` `src/cadrumo_harness/_data`
- `S03` `D` `src/cadrumo_harness/_resources.py`
- `S03` `D` `src/cadrumo_harness/resources.py`
- `S03` `D` `src/cadrumo_harness/_skill_metadata.py`
- `S03` `D` `src/cadrumo_harness/workspace.py`
- `S03` `D` `src/cadrumo_harness/tests`
- `S03` `D` `dev/harness_data`
- `S03` `D` `dev/agent_eval/tests/test_rule_surface_conformance.py`
- `S03` `M` `dev/agent_eval/_runner.py`
- `S03` `M` `dev/agent_eval/_models.py`
- `S03` `M` `dev/agent_eval/tests/test_modelo_130_golden.py`
- `S03` `M` `dev/packaging/tests/test_verdict_cache_not_distributed.py`
- `S03` `M` `pyproject.toml`
- `S03` `M` `.importlinter`
- `S03` `M` `dev/quality/metadata/import_load_targets.json`
- `S03` `M` `dev/quality/metadata/import_load_targets.cadrumo_harness.json`
- `S03` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S03` `verify:` `lint-imports --config .importlinter --no-cache` -> `pass`
- `S03` `verify:` `pytest src/cadrumo_harness dev/agent_eval` -> `pass`
- `S03` `verify:` `pytest -n0 dev/packaging/tests/test_verdict_cache_not_distributed.py` -> `pass`
- `S03` `verify:` `ty check src/cadrumo_harness dev/agent_eval` -> `pass`
- `S03` `by:` `implementation-engineer-high`

## Notes

- `S01` No skill or rule semantic changes found after the cadrumo-agent fork date (2026-10-16T09:18:40+02:00); last rules/skills commit before e4188cc067 was ca427b0666 (2026-10-15), which predates the fork. The only post-fork Cadrumo commit touching `src/cadrumo_harness/_data/agent` is 72cd94bc66, editing reference/command-operations.md only; that generated operation catalogue is explicitly out of scope per the plan (cadrumo-agent derives operation knowledge from MCP discovery) and no cadrumo-agent skill references it. No port was applicable; no cadrumo-agent file was edited.
- `S01` Concurrent cadrumo-agent dirty files (rules/cadrumo-operator-operating-rules.md, skills/cadrumo-alta-contribuyente/SKILL.md, skills/cadrumo-calendario-fiscal/SKILL.md) were left untouched per instruction; no port was owed to them since no qualifying post-fork Cadrumo-side change existed.
- `S03` Seven integration tests in `dev/agent_eval` `(test_under_declaration_golden.py,` `test_response_provenance_golden.py)` fail with 'CLI scenario requires the injected `invoke_cli` fixture'. No file on that failure path changed in this plan; the seam dates from the 2026-10-19 CLI-rename repair and belongs to the concurrent full-suite repair work.
