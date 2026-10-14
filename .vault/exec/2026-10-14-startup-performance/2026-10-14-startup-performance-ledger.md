---
tags:
  - '#exec'
  - '#startup-performance'
date: '2026-10-14'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:e7ae7902d83af6fb5ba9fc7db6b109f82f2f6c1c8abcff6a550879610f58bee0'
related:
  - "[[2026-10-14-startup-performance-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `startup-performance` ledger

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

- `S01` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S01` `A` `src/cadrumo/entrypoints/google_export_operation_composition.py`
- `S01` `M` `src/cadrumo/entrypoints/tests/test_google_effect_imports.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/tests/test_google_operation.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_worker_startup_import_graph.py`
- `S01` `verify:` `eager registry parity probe (283 operations, identical contract-set digest, 148 groups)` -> `pass`
- `S01` `verify:` `pytest test_google_effect_imports test_google_operation test_operation_registry_imports test_operation_execution_imports test_operation_composition` -> `pass`
- `S01` `verify:` `pytest test_worker_startup_import_graph::test_the_exclusion_probe_bites` -> `pass`
- `S01` `by:` `implementation-high`

## Notes

- `S01` Commit 311cf0b5a1 was not made by this worker; it swept this Step's uncommitted `google_export_operation_composition.py,` test edits and the plan together with unrelated work under a startup-performance subject. `operation_composition.py` itself landed in 925db5295c.
- `S01` `test_a_ready_worker_excludes_the_operation_graph` fails on `cadrumo.domain.provider_settings.catalog` from the concurrent provider-settings work, not this Step.
