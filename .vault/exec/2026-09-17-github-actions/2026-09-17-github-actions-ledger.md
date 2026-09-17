---
tags:
  - '#exec'
  - '#github-actions'
date: '2026-09-17'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:f999a0f7da13e18f0a99c37ce9c44509aa451d53c5b80d12108e474436fc69b9'
related:
  - "[[2026-09-17-github-actions-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `github-actions` ledger

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
- `S12` `A` `dev/ci/change_scope.py`
- `S12` `A` `dev/ci/tests/test_change_scope.py`
- `S12` `M` `pyproject.toml`
- `S12` `verify:` `pytest dev/ci/tests/test_change_scope.py` -> `pass`
- `S12` `by:` `ci-scope`
- `S01` `A` `.github/actions/setup/action.yml`
- `S01` `verify:` `just check-workflows` -> `pass`
- `S01` `by:` `ci-setup`
- `S02` `M` `justfile`
- `S02` `verify:` `just --list` -> `pass`
- `S02` `by:` `ci-setup`

