---
tags:
  - '#exec'
  - '#application-distribution'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:03fa7ed7d14a998a5cf1ad09c9853edc2b4c3416e8893a1743ee09b5ff28c760'
related:
  - "[[2026-10-04-application-distribution-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `application-distribution` ledger

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

- `S01` `M` `src/cadrumo/core/product_identity.py`
- `S01` `M` `src/cadrumo/core/tests/test_product_identity.py`
- `S01` `A` `dev/packaging/native/identity.py`
- `S01` `A` `dev/packaging/tests/test_distribution_identity.py`
- `S01` `verify:` `pytest identity suites 17 passed` -> `pass`
- `S01` `verify:` `ruff and ty focused identity` -> `pass`
- `S02` `M` `CMakeLists.txt`
- `S02` `A` `native/cmake/Identity.cmake`
- `S02` `A` `native/cmake/CompilePolicy.cmake`
- `S02` `M` `native/cmake/Packaging.cmake`
- `S02` `M` `native/cmake/platforms/Windows.cmake`
- `S02` `M` `dev/packaging/native/metadata.py`
- `S02` `M` `dev/packaging/native/platforms/windows.py`
- `S02` `M` `native/interpreter/windows/python.c`
- `S02` `verify:` `cmake configure windows-x64` -> `pass`
- `S02` `verify:` `Release interpreter and ABI consumer build` -> `pass`
- `S02` `verify:` `ctest platform 3 tests` -> `pass`
- `S03` `A` `dev/packaging/native/installation.py`
- `S03` `A` `dev/packaging/tests/test_native_installation.py`
- `S03` `A` `native/cmake/distribution/CMakeLists.txt`
- `S03` `A` `native/cmake/distribution/VerifyInstall.cmake.in`
- `S03` `M` `native/desktop/CMakeLists.txt`
- `S03` `M` `native/desktop/scripts/host.mjs`
- `S03` `M` `native/CONTRACT.md`
- `S03` `M` `dev/packaging/native/identity.py`
- `S03` `M` `dev/packaging/tests/test_distribution_identity.py`
- `S03` `M` `native/cmake/CompilePolicy.cmake`
- `S03` `verify:` `34 focused identity and installation tests` -> `pass`
- `S03` `verify:` `Ruff format lint and ty` -> `pass`
- `S03` `verify:` `Linux synthetic DEB prefix install and uninstall` -> `pass`
- `S03` `verify:` `Windows real runtime ZIP install smoke and modified-file-preserving uninstall` -> `pass`
- `S03` `verify:` `GCC compile policy fixture build and execution` -> `pass`
- `S03` `verify:` `Node host syntax and desktop identity configure` -> `pass`
- `S05` `A` `native/cmake/BuildPaths.cmake`
- `S05` `A` `dev/packaging/native/build_paths.py`
- `S05` `M` `dev/packaging/native/cleanup.py`
- `S05` `M` `dev/packaging/native/cmake_build.py`
- `S05` `M` `dev/packaging/native/artifact_verify.py`
- `S05` `M` `native/CMakeLists.txt`
- `S05` `M` `native/cmake/Identity.cmake`
- `S05` `M` `native/cmake/Packaging.cmake`
- `S05` `M` `native/cmake/Rust.cmake`
- `S05` `M` `native/cmake/platforms/Windows.cmake`
- `S05` `M` `native/application/CMakeLists.txt`
- `S05` `M` `native/cmake/CPackProject.cmake.in`
- `S05` `M` `native/cmake/Artifact.cmake.in`
- `S05` `M` `native/CONTRACT.md`
- `S05` `A` `dev/packaging/tests/test_build_paths.py`
- `S05` `M` `dev/packaging/tests/test_native_artifact_identity.py`
- `S05` `verify:` `cmake --preset windows-x64` -> `pass`
- `S05` `verify:` `pytest test_build_paths.py test_native_artifact_identity.py (11 tests)` -> `pass`
- `S05` `verify:` `ruff check and format; ty check changed Python helpers` -> `pass`
- `S05` `M` `native/desktop/CMakeLists.txt`
- `S05` `A` `native/desktop/scripts/build-paths.mjs`
- `S05` `A` `native/desktop/scripts/build-paths.d.mts`
- `S05` `M` `native/desktop/scripts/tauri.mjs`
- `S05` `M` `native/desktop/frontend/vite.config.ts`
- `S05` `M` `native/desktop/frontend/playwright.config.ts`
- `S05` `M` `native/desktop/tests/headless.test.mjs`
- `S05` `A` `native/desktop/tests/build-paths.test.mjs`
- `S05` `M` `native/cmake/distribution/CMakeLists.txt`
- `S05` `M` `native/cmake/distribution/VerifyInstall.cmake.in`
- `S05` `M` `dev/packaging/native/installation.py`
- `S05` `M` `dev/packaging/tests/test_native_installation.py`
- `S05` `verify:` `pytest native installation, build paths, artifact identity: 33 passed, 2 POSIX skips` -> `pass`
- `S05` `verify:` `CMake desktop-paths-test, desktop-frontend-build, desktop-frontend-check` -> `pass`
- `S05` `verify:` `ruff and ty affected Python modules` -> `pass`

## Notes

- `S03` Native MSI RPM macOS and full platform lifecycle evidence remain in S04; WiX UI extension setup requires operator EULA acceptance.
- `S05` S05 remains open. Automatic approval review rejected both PowerShell deletion attempts for the enumerated disposable build files and directories, including literal absolute paths, with blocked by policy and no further reason. No build clutter was removed. Source-build paths are centralized; desktop and standalone distribution output integration and physical cleanup remain pending.
- `S05` Extended CMake path ownership to desktop and native installation staging. Removed development-status labels from build-framework documentation. Existing physical clutter remains blocked by the previously recorded deletion rejection; S05 remains open.
