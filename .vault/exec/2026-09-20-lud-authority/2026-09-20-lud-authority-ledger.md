---
tags:
  - '#exec'
  - '#lud-authority'
date: '2026-09-20'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:a8867b7d360dde90c5581ad99a0b3027354fa8d70aaef10aa3e34ce73c6ff3b4'
related:
  - "[[2026-09-20-lud-authority-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `lud-authority` ledger

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
- `S01` `M` `src/cadrumo/core/storage_materialization.py`
- `S01` `M` `src/cadrumo/core/storage_taxonomy_locations.py`
- `S01` `M` `src/cadrumo/core/tests/test_ensure_storage_tree.py`
- `S01` `A` `.vault/reference/2026-09-20-lud-authority-reference.md`
- `S01` `A` `.vault/adr/2026-09-20-lud-authority-adr.md`
- `S01` `A` `.vault/plan/2026-09-20-lud-authority-plan.md`
- `S01` `A` `.vault/index/lud-authority.index.md`
- `S01` `verify:` `ruff and three module type checkers` -> `pass`
- `S01` `by:` `principal executor`

