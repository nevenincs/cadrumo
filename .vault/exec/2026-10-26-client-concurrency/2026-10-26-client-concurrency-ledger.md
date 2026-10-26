---
tags:
  - '#exec'
  - '#client-concurrency'
date: '2026-10-26'
modified: '2026-10-26'
body_schema: 'body-v2'
body_hash: 'sha256:da93c212991009b4b9c5dc6b0d6432d3c0c5ccb1dbbccfcb829316fa7924a8cc'
related:
  - "[[2026-10-26-client-concurrency-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `client-concurrency` ledger

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

- `S01` `M` `src/cadrumo_client/transport/operation_changes.py`
- `S01` `M` `src/cadrumo_client/transport/operation_controller.py`
- `S01` `A` `src/cadrumo_client/transport/tests/test_operation_changes.py`
- `S01` `M` `src/cadrumo_client/transport/tests/test_operation_controller_binding.py`
- `S01` `M` `src/cadrumo_client/transport/tests/test_channel_readiness_wait.py`
- `S01` `verify:` `uv run --no-sync pytest src/cadrumo_client/transport/tests -q` -> `pass`
- `S01` `verify:` `uv run --no-sync pytest src/cadrumo_client/transport/tests/test_operation_changes.py src/cadrumo_client/transport/tests/test_operation_controller_binding.py -q` -> `pass`
- `S01` `verify:` `uv run --no-sync pytest src/cadrumo_client/transport/tests/test_operation_changes.py src/cadrumo_client/transport/tests/test_channel_readiness_wait.py -m '' -q` -> `pass`
- `S01` `verify:` `just check-types --count` -> `pass`

## Notes

- `S01` Concurrent runtime session supplied `verified_transport` disconnect-finally fix and overlapping native-channel tests; combined behavior passed. Benchmark scratch lives in .tmp/client-concurrency: 30000 cues, callbacks 30000 to 30, median burst 13.566 ms to 0.229 ms.
