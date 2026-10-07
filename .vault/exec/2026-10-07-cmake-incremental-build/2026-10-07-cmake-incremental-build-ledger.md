---
tags:
  - '#exec'
  - '#cmake-incremental-build'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:f51b592fb2d991e6197fb4d123ee9b02dd735e47c761a678a6bada321b257b15'
related:
  - "[[2026-10-07-cmake-incremental-build-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `cmake-incremental-build` ledger

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

- `S01` `M` `native/desktop/CMakeLists.txt`
- `S01` `M` `native/desktop/scripts/tauri.mjs`
- `S01` `M` `native/desktop/scripts/frontend-install.mjs`
- `S01` `A` `native/desktop/scripts/content-build.mjs`
- `S01` `A` `native/desktop/scripts/frontend-build.mjs`
- `S01` `A` `native/desktop/tests/content-build.test.mjs`
- `S01` `A` `native/desktop/tests/frontend-clean.test.mjs`
- `S01` `verify:` `node --test native/desktop/tests/content-build.test.mjs native/desktop/tests/backend-snapshot.test.mjs native/desktop/tests/frontend-clean.test.mjs` -> `pass`
- `S01` `verify:` `npm run check (native/desktop/frontend)` -> `pass`
- `S01` `verify:` `cmake desktop-chrome desktop-palette repeated output timestamp check` -> `pass`
- `S02` `M` `native/CMakeLists.txt`
- `S02` `M` `native/application/CMakeLists.txt`
- `S02` `M` `native/platform/Cargo.toml`
- `S02` `A` `native/cmake/Contract.cmake`
- `S02` `M` `native/cmake/PackageInputs.cmake`
- `S02` `M` `native/cmake/Manager.cmake`
- `S02` `M` `native/cmake/platforms/Windows.cmake`
- `S02` `M` `native/cmake/platforms/Posix.cmake`
- `S02` `M` `dev/packaging/native/cmake_build.py`
- `S02` `M` `dev/packaging/native/provision.py`
- `S02` `M` `dev/packaging/native/generate.py`
- `S02` `M` `dev/packaging/native/metadata.py`
- `S02` `A` `dev/packaging/native/stable_output.py`
- `S02` `M` `dev/packaging/native/platforms/windows.py`
- `S02` `A` `dev/packaging/native/tests/test_incremental_generation.py`
- `S02` `M` `dev/packaging/native/tests/test_cmake_package_inputs.py`
- `S02` `verify:` `focused Python fingerprint and native target tests (29 tests)` -> `pass`
- `S02` `verify:` `ruff check and format --check changed Python files` -> `pass`
- `S02` `verify:` `ty check changed Python files` -> `pass`
- `S02` `verify:` `cmake --preset windows-x64` -> `pass`
- `S02` `verify:` `cmake native static shared consumer python target builds and unchanged timestamp comparison` -> `pass`

## Notes

- `S02` Authority compiler fingerprint remains intentionally conservative in its canonical owner; this does not establish minimal compiler invalidation.
