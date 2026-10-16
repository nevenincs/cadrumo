---
tags:
  - '#exec'
  - '#idle-churn'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:5d4fe5542f122bb57eb731fcaeed3dca0c4ba3511ab16c68e8b3903f082101ee'
related:
  - "[[2026-10-16-idle-churn-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `idle-churn` ledger

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

- `S01` `M` `src/cadrumo_client/contracts/service_access.py`
- `S01` `M` `src/cadrumo/core/path_confinement.py`
- `S01` `M` `src/cadrumo_runtime/adapters/service_verification.py`
- `S01` `M` `src/cadrumo_runtime/host/profile_connection_extension_records.py`
- `S01` `M` `src/cadrumo_runtime/host/profile_connection_services.py`
- `S01` `M` `src/cadrumo_runtime/host/tests/test_service_records.py`
- `S01` `A` `src/cadrumo_runtime/adapters/tests/test_service_verification.py`
- `S01` `verify:` `pytest -n0 -m '' test_service_verification.py test_service_records.py` -> `pass`
- `S01` `verify:` `ruff check + ruff format --check + ty check on touched files` -> `pass`

## Notes

- `S01` `profile_connection_services.py` interleaves with another session's uncommitted lease-guard and refusal-check hunks; its claim and admission recheck stays uncommitted until those land, while HEAD's full verification there still works with the new verifier.
