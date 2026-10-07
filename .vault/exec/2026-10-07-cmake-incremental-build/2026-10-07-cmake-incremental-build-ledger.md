---
tags:
  - '#exec'
  - '#cmake-incremental-build'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:e47f2d72d69225118c726065eaa50ab853f4de1f2cdb8d7bc52710615aa09fef'
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
- `S03` `M` `justfile`
- `S03` `M` `native/cmake/BuildPaths.cmake`
- `S03` `M` `native/cmake/Docs.cmake`
- `S03` `M` `native/cmake/Identity.cmake`
- `S03` `M` `native/cmake/Packaging.cmake`
- `S03` `M` `native/cmake/distribution/CMakeLists.txt`
- `S03` `A` `native/cmake/Authority.cmake`
- `S03` `A` `native/cmake/Bootstrap.cmake`
- `S03` `A` `native/cmake/CachedCommand.cmake`
- `S03` `A` `native/cmake/CleanBuilder.cmake`
- `S03` `A` `native/cmake/Cleanup.cmake`
- `S03` `M` `dev/packaging/native/cleanup.py`
- `S03` `A` `dev/packaging/native/authority_build.py`
- `S03` `A` `dev/packaging/native/cached_command.py`
- `S03` `A` `dev/packaging/native/distribution_prepare.py`
- `S03` `A` `dev/packaging/native/tests/test_authority_build_fingerprints.py`
- `S03` `A` `dev/packaging/native/tests/test_builder_cleanup.py`
- `S03` `A` `dev/packaging/native/tests/test_cached_command.py`
- `S03` `A` `dev/packaging/native/tests/test_cleanup.py`
- `S03` `A` `dev/packaging/native/tests/test_distribution_prepare.py`
- `S03` `verify:` `pytest cleanup cached command distribution builder tests (13 tests)` -> `pass`
- `S03` `verify:` `pytest authority fingerprints included final producer suite` -> `pass`
- `S03` `verify:` `ruff check and format --check changed Python files` -> `pass`
- `S03` `verify:` `ty check changed Python files` -> `pass`
- `S03` `verify:` `cmake --preset windows-x64` -> `pass`

## Notes

- `S02` Authority compiler fingerprint remains intentionally conservative in its canonical owner; this does not establish minimal compiler invalidation.
- `S03` Full application ZIP acceptance is assigned to S04 and remains pending behind the foreign documentation build; real install/CPack fixtures pass.
