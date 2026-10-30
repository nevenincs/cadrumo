---
tags:
  - '#exec'
  - '#test-suite-budget'
date: '2026-10-30'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:6cfa23466ac01806e5b2baaa307ebbd990229a89e490aa5c2a665047af80f97f'
related:
  - "[[2026-10-30-test-suite-budget-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `test-suite-budget` ledger

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

- `S01` `M` `src/cadrumo/entrypoints/tests/registered_executor_case_support.py`
- `S01` `verify:` `pytest test_operation_subject_binding test_registered_executor_conformance` -> `pass`
