---
tags:
  - '#exec'
  - '#runtime-manager-architecture'
date: '2026-10-04'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:3e2905210505f3d42f6d12f9fadf0c1249ccd20526b4cfe64c43cff75ba5131e'
related:
  - "[[2026-10-04-runtime-manager-architecture-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `runtime-manager-architecture` ledger

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

- `S06` `R` `src/cadrumo/adapters/local_runtime/manager_commands.py` -> `src/cadrumo/adapters/local_runtime/containment_commands.py`
- `S06` `R` `src/cadrumo/adapters/local_runtime/tests/test_manager_command_sync.py` -> `src/cadrumo/adapters/local_runtime/tests/test_containment_command_sync.py`
- `S06` `M` `src/cadrumo/adapters/local_runtime/linux_worker_process.py`
- `S06` `M` `src/cadrumo/adapters/local_runtime/macos_worker_process.py`
- `S06` `M` `src/cadrumo/adapters/local_runtime/tests/test_linux_worker_containment.py`
- `S06` `M` `src/cadrumo/adapters/local_runtime/tests/test_macos_worker_containment.py`
- `S06` `M` `src/cadrumo/adapters/local_runtime/tests/test_macos_worker_process.py`
- `S06` `M` `src/cadrumo/entrypoints/runtime/tests/linux_worker_parent_fixture.py`
- `S06` `M` `src/cadrumo/entrypoints/runtime/tests/macos_worker_parent_fixture.py`
- `S06` `M` `src/cadrumo/entrypoints/runtime/tests/test_linux_worker_launch_contract.py`
- `S06` `M` `dev/quality/metadata/import_load_targets.json`
- `S06` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S06` `verify:` `focused pytest (5 files) 73 passed 19 platform-skipped` -> `pass`
- `S06` `verify:` `ruff check and format --check on touched files` -> `pass`
- `S06` `verify:` `ty check touched files win32 linux darwin` -> `pass`
- `S06` `verify:` `just check-import-boundaries` -> `fail`
- `S06` `verify:` `just check-types` -> `fail`

## Notes

- `S06` Repo-wide gates failed outside this Step: concurrent writers changed the governed tree mid-run and a hard finding in `test_censo_import_fact_payload.py;` check-types diagnostics name only other files while the shared .venv was being rebuilt. Mixed-owner files staged with only this Step's hunks.
