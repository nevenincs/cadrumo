---
tags:
  - '#exec'
  - '#tui-all-mcp-integration'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:a07d2ad0bccaaace50448670397f0ad22646a5d0479eb09c63339cb890a8a940'
related:
  - "[[2026-10-03-tui-all-mcp-integration-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `tui-all-mcp-integration` ledger

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

- `S01` `M` `src/cadrumo/application/command_search/index.py`
- `S01` `M` `src/cadrumo/application/corpus_search/runtime.py`
- `S01` `M` `src/cadrumo_harness/mcp/admitted_operations.py`
- `S01` `M` `src/cadrumo_harness/mcp/protocol_contract.py`
- `S01` `M` `src/cadrumo_harness/mcp/runtime_adapter.py`
- `S01` `M` `docs/how-to/connect-an-agent.md`
- `S01` `A` `src/cadrumo_harness/mcp/corpus_query.py`
- `S01` `A` `src/cadrumo_harness/mcp/operation_search.py`
- `S01` `A` `src/cadrumo_harness/mcp/tests/test_corpus_search_tool.py`
- `S01` `A` `src/cadrumo_harness/mcp/tests/test_operation_search_tool.py`
- `S01` `A` `src/cadrumo_harness/mcp/tests/test_runtime_authority.py`
- `S01` `verify:` `MCP/search discovery and authority-pinning cohort82tests` -> `pass`
- `S01` `verify:` `changed discovery source Ruff and format` -> `pass`
- `S01` `by:` `history`
- `S01` `M` `conftest.py`
- `S01` `D` `src/cadrumo_harness/mcp/tests/conftest.py`
- `S01` `verify:` `MCP82tests after repository fixture relocation` -> `pass`
