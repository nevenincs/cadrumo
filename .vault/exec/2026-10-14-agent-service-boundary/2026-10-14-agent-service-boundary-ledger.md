---
tags:
  - '#exec'
  - '#agent-service-boundary'
date: '2026-10-14'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:2af7c4d1231cc54087c48c1b9a9b15128f9f1fd9d97264b0a4ae99cc74e2db06'
related:
  - "[[2026-10-14-agent-service-boundary-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `agent-service-boundary` ledger

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

- `S03` `verify:` `locator-check: src/cadrumo_agent_service and src/cadrumo_mcp present; cadrumo_harness absent` -> `pass`
- `S03` `by:` `plan-closure`
- `S04` `verify:` `locator-check: native/desktop/src-tauri/src/agent/launcher.rs:129` -> `pass`
- `S04` `by:` `plan-closure`
- `S05` `verify:` `locator-check: pyproject.toml:142,144,250` -> `pass`
- `S05` `by:` `plan-closure`
