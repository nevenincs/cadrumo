---
tags:
  - '#exec'
  - '#cmake-e2e-build'
date: '2026-10-08'
modified: '2026-10-08'
body_schema: 'body-v2'
body_hash: 'sha256:e90cbc1bbad8437171474deee829cf57ed646c02197122a1fb3f48859d6cb2a1'
related:
  - "[[2026-10-08-cmake-e2e-build-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `cmake-e2e-build` ledger

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

- `S01` `M` `native/cmake/Docs.cmake`
- `S01` `M` `native/cmake/Packaging.cmake`
- `S01` `M` `native/desktop/CMakeLists.txt`
- `S01` `M` `native/CONTRACT.md`
- `S01` `M` `src/cadrumo/entrypoints/cli/runtime_modelo_verification.py`
- `S01` `verify:` `cmake --preset windows-x64` -> `pass`
- `S01` `verify:` `cmake --build --preset release --target user_docs_sequences_check --parallel 2 (how-to/modelo-390)` -> `pass`
- `S01` `M` `dev/packaging/native/docs_build.py`
- `S01` `M` `dev/packaging/native/tests/test_docs_shared_site.py`
- `S01` `verify:` `cmake --build --preset release --target user_docs_driver_test --parallel 2` -> `pass`
- `S01` `verify:` `cmake --build --preset release --target desktop-host-build --parallel 4` -> `pass`
- `S01` `verify:` `cmake --build --preset release --target desktop-run (before package assembly)` -> `fail`

## Notes

- `S01` S01 remains open. Full page check passed; desktop-headless-test is running and waiting for the shared docs cache held by windows-installers-x64. No executable acceptance yet.
- `S01` User explicitly requested package assembly after the Session 0 launch reported a missing package. Shared-cache reuse is OFF for this preset; all validation remains enabled. The active desktop-headless-test build is executing documentation checks before bundle assembly and Session 0 acceptance.
