---
tags:
  - '#exec'
  - '#component-on-demand'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:23539a45016201784d52f3d307c47573f6d6324e4100e739c306206b68129899'
related:
  - "[[2026-10-24-component-on-demand-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `component-on-demand` ledger

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

- `S01` `M` `src/cadrumo/application/provisioning_contracts.py`
- `S01` `M` `src/cadrumo/application/local_reader.py`
- `S01` `M` `src/cadrumo/application/tests/test_local_reader.py`
- `S01` `verify:` `pytest local_reader, provisioning, llm reader, batch ingest and evidence CLI suites (144)` -> `pass`
- `S01` `verify:` `ruff check/format, ty, lint-imports` -> `pass`
