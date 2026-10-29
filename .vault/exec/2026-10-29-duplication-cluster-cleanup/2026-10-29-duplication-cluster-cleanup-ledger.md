---
tags:
  - '#exec'
  - '#duplication-cluster-cleanup'
date: '2026-10-29'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:2011ff2e24d73c533eddf2c2f605740a6e77fdec4dc3ced89b1bf547d72e9e01'
related:
  - "[[2026-10-29-duplication-cluster-cleanup-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `duplication-cluster-cleanup` ledger

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

- `S01` `M` `src/cadrumo/entrypoints/tui/aeat_sync/screens.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/aeat_sync/tests/test_aeat_sync_workspace.py`
- `S01` `verify:` `uv run --no-sync pytest -n 0 -m integration src/cadrumo/entrypoints/tui/aeat_sync/tests/test_aeat_sync_workspace.py -q` -> `pass`
- `S01` `verify:` `scoped Ruff check and format and Windows ty` -> `pass`
- `S01` `by:` `Terra 6.1 xhigh`
- `S02` `M` `src/cadrumo/application/modelo/workspace_schema.py`
- `S02` `M` `src/cadrumo/application/modelo/workspace_graded.py`
- `S02` `A` `src/cadrumo/application/modelo/workspace_baseline.py`
- `S02` `A` `src/cadrumo/application/modelo/tests/test_workspace_baseline.py`
- `S02` `M` `src/cadrumo/adapters/persistence/profile/tests/test_workspace.py`
- `S02` `verify:` `baseline/model/producer focused pytest 54 cases` -> `pass`
- `S02` `verify:` `real persistence work-review pytest 21 cases` -> `pass`
- `S02` `verify:` `static Workspace pytest 27 cases` -> `pass`
- `S02` `verify:` `five-file Ruff check and format and Windows ty` -> `pass`
- `S02` `verify:` `just generate-import-load-targets` -> `pass`
- `S02` `by:` `Sol 6.1 high`
- `S03` `M` `src/cadrumo/entrypoints/cli/app_live_commands.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_operation_filed_single.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_operation_filed_bulk.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_operation_filed_source.py`
- `S03` `verify:` `filed capture owning and complementary pytest 59 cases` -> `pass`
- `S03` `verify:` `scoped Ruff check and format and Windows ty` -> `pass`
- `S03` `by:` `Terra 6.1 xhigh`
- `S04` `M` `src/cadrumo_runtime/host/profile_connection_operations.py`
- `S04` `M` `src/cadrumo_runtime/host/tests/test_view_stream_relay.py`
- `S04` `M` `src/cadrumo_runtime/host/tests/test_profile_connections.py`
- `S04` `verify:` `runtime view stream integration pytest 26 cases` -> `pass`
- `S04` `verify:` `runtime profile connections integration pytest 5 cases` -> `pass`
- `S04` `verify:` `three-file Ruff check and format and Windows ty` -> `pass`
- `S04` `by:` `Terra 6.1 xhigh`
- `S05` `M` `src/cadrumo/application/workbench_generation_reader.py`
- `S05` `M` `src/cadrumo/application/tests/test_workbench_generation.py`
- `S05` `verify:` `workbench generation and capture-memory pytest 46 cases` -> `pass`
- `S05` `verify:` `workbench capture order and phase controls 5 cases` -> `pass`
- `S05` `verify:` `two-file Ruff check and format and Windows ty` -> `pass`
- `S05` `by:` `Sol 6.1 high`
- `S05` `verify:` `parent combined Ruff and formatting and Windows ty on 19 cleanup files` -> `pass`
- `S06` `M` `src/cadrumo/application/auth/operator_cleanup.py`
- `S06` `M` `src/cadrumo/application/auth/operator_revocation.py`
- `S06` `A` `src/cadrumo/application/auth/tests/test_operator_cleanup_matching.py`
- `S06` `M` `src/cadrumo/adapters/persistence/profile/tests/test_operator_transaction_recovery.py`
- `S06` `verify:` `auth matching and real durable cleanup combined pytest 58 cases` -> `pass`
- `S06` `verify:` `exact transaction concurrency case pytest 1 case` -> `pass`
- `S06` `verify:` `four-file Ruff check and format and Windows ty` -> `pass`
- `S06` `verify:` `unchanged duplication scanner post-refinement no auth pair` -> `pass`
- `S06` `by:` `Sol 6.1 high`
- `S07` `M` `src/cadrumo/entrypoints/tests/test_reader_consumer_gating.py`
- `S07` `verify:` `reader gating focused regression pytest 1 case` -> `pass`
- `S07` `verify:` `reader consumer gating owning integration pytest 41 cases` -> `pass`
- `S07` `verify:` `scoped Ruff and format and Windows ty` -> `pass`
- `S07` `by:` `Terra 6.1 xhigh`

## Notes

- `S02` Generated metadata was adopted by concurrent commit 29d0663d16; no foreign metadata hunks restaged.
- `S03` Production mapping and bulk test adopted by concurrent commit b6e52594fb alongside foreign output-root feature; checkpoint retains remaining test delta.
- `S04` Existing worker-loss writer thread warning `CONNECTION_CLOSED` retained in test evidence.
- `S05` Reader source adopted by concurrent commit b9003df9be with foreign calendar/staleness changes preserved; authored patch and receipt retain attribution.
- `S05` S05 source already present in b9003df9be; separate remaining test checkpoint follows after concurrent Git lock delayed S04 staging.
- `S06` Intermediate 21/22 and 57/58 durable failures were investigated with preimage controls. One-line test readiness signal moved after custody fixture entry; assertions and production session policy unchanged. Final combined 58 passed.
- `S07` Broad gate reproduced stale condition-ID assertion. Both refusal codes intentionally share the completion condition; exact expected refusal-evidence diagnostic replaces obsolete substring oracle. No production change.
