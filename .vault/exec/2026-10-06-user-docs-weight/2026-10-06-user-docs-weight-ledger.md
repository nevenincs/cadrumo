---
tags:
  - '#exec'
  - '#user-docs-weight'
date: '2026-10-06'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:b071186bbd3fa07e27ca3d48f081011ada6b0c278c96b377ae87f4d830bbfb2a'
related:
  - "[[2026-10-06-user-docs-weight-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `user-docs-weight` ledger

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

- `S01` `A` `dev/docs/shared_structure.py`
- `S01` `A` `dev/docs/tests/test_shared_structure.py`
- `S01` `verify:` `pytest dev/docs/tests/test_shared_structure.py` -> `pass`
- `S01` `verify:` `ruff check and format on both files` -> `pass`
- `S01` `verify:` `ty check on both files` -> `pass`
- `S01` `verify:` `factor and compose the four desktop roots built 2026-10-06 (561 pages, 2244 comparisons, 0 mismatches)` -> `pass`
- `S02` `A` `dev/docs/language_roots.py`
- `S02` `A` `dev/docs/tests/test_language_roots.py`
- `S02` `verify:` `pytest dev/docs/tests/test_language_roots.py dev/docs/tests/test_shared_structure.py (23 tests)` -> `pass`
- `S02` `verify:` `ruff check and format on both files` -> `pass`
- `S02` `verify:` `ty check on both files` -> `pass`
- `S02` `verify:` `store the four desktop roots built 2026-10-06 (382.1 MB, 62720 files) as 156.0 MB and compare every file composed back (0 differences)` -> `pass`
