---
tags:
  - '#exec'
  - '#git-free-tooling'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:96ff87efc272c177a8e325ccc8e97a80c16aaaa59b1fbc41d1724897139d19c6'
related:
  - "[[2026-10-07-git-free-tooling-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `git-free-tooling` ledger

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

- `S01` `M` `dev/source_tree.py`
- `S01` `M` `dev/env/clean.py`
- `S01` `M` `dev/env/_dotenv.py`
- `S01` `M` `dev/env/tests/test_clean.py`
- `S01` `M` `dev/env/tests/test_dotenv.py`
- `S01` `M` `dev/registry/edition_round_trip.py`
- `S01` `M` `dev/deploy/docs_delivery_policy.py`
- `S01` `M` `native/cmake/BuildNumber.cmake`
- `S01` `M` `dev/packaging/native/tests/test_cmake_build_number.py`
- `S01` `verify:` `focused tests: 44 passed` -> `pass`
- `S01` `verify:` `scoped ruff lint and format` -> `pass`
- `S01` `verify:` `scoped ty` -> `pass`
