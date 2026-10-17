---
tags:
  - '#exec'
  - '#windows-package-identity'
date: '2026-10-16'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:bffe0eb1bb6871eb8d02a8cb85dac834be1ff778faa372183b56aa1d58228e53'
related:
  - "[[2026-10-16-windows-package-identity-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `windows-package-identity` ledger

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

- `S01` `M` `dev/packaging/native/identity.py`
- `S01` `M` `dev/packaging/tests/test_distribution_identity.py`
- `S01` `verify:` `pytest dev/packaging/tests/test_distribution_identity.py` -> `pass`
- `S02` `M` `dev/packaging/native/platforms/windows.py`
- `S02` `M` `dev/packaging/native/platforms/linux.py`
- `S02` `M` `dev/packaging/native/platforms/macos.py`
- `S02` `M` `dev/packaging/native/metadata.py`
- `S02` `M` `dev/packaging/native/platforms/tests/test_windows.py`
- `S02` `M` `native/interpreter/windows/host.rc`
- `S02` `M` `native/cmake/platforms/Windows.cmake`
- `S02` `M` `native/cmake/Manager.cmake`
- `S02` `M` `native/manager/build.rs`
- `S02` `M` `dev/quality/metadata/import_load_targets.json`
- `S02` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S02` `verify:` `cmake --build --preset debug --target app-payload embedded-manifest check` -> `pass`
- `S02` `verify:` `Release app-payload embedded-manifest check` -> `pass`
- `S03` `A` `native/desktop/src-tauri/windows/desktop.manifest`
- `S03` `M` `native/desktop/src-tauri/build.rs`
- `S03` `M` `native/desktop/scripts/tauri.mjs`
- `S03` `M` `native/desktop/tests/packaged/host.mjs`
- `S03` `M` `.gitignore`
- `S03` `verify:` `Debug and Release desktop builds` -> `pass`
- `S04` `A` `dev/packaging/native/package_identity.py`
- `S04` `A` `dev/packaging/native/tests/test_package_identity.py`
- `S04` `verify:` `pytest dev/packaging/native/tests/test_package_identity.py` -> `pass`
- `S05` `M` `dev/packaging/native/package_identity.py`
- `S05` `verify:` `package_identity register --build build/windows-x64` -> `pass`
- `S05` `verify:` `GetPackageFullName on cadrumo.exe, cadrumo-runtime.exe and msedgewebview2.exe children` -> `pass`

## Notes

- `S02` RC truncates macro names at 31 characters and the Visual Studio generator ignores `COMPILE_LANGUAGE:RC;` the define is a host.rc source property.
- `S03` Tauri embeds the manifest with layout whitespace collapsed; registration compares parsed XML.
- `S05` Task Manager grouping and signed-in agent processes await operator observation.
