---
tags:
  - '#exec'
  - '#application-distribution'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:4f843b2671e7ed47d0c893fc760adabd2c1f9153d2eef1ffc0679537b9a62504'
related:
  - "[[2026-10-04-application-distribution-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `application-distribution` ledger

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

- `S01` `M` `src/cadrumo/core/product_identity.py`
- `S01` `M` `src/cadrumo/core/tests/test_product_identity.py`
- `S01` `A` `dev/packaging/native/identity.py`
- `S01` `A` `dev/packaging/tests/test_distribution_identity.py`
- `S01` `verify:` `pytest identity suites 17 passed` -> `pass`
- `S01` `verify:` `ruff and ty focused identity` -> `pass`
- `S02` `M` `CMakeLists.txt`
- `S02` `A` `native/cmake/Identity.cmake`
- `S02` `A` `native/cmake/CompilePolicy.cmake`
- `S02` `M` `native/cmake/Packaging.cmake`
- `S02` `M` `native/cmake/platforms/Windows.cmake`
- `S02` `M` `dev/packaging/native/metadata.py`
- `S02` `M` `dev/packaging/native/platforms/windows.py`
- `S02` `M` `native/interpreter/windows/python.c`
- `S02` `verify:` `cmake configure windows-x64` -> `pass`
- `S02` `verify:` `Release interpreter and ABI consumer build` -> `pass`
- `S02` `verify:` `ctest platform 3 tests` -> `pass`
