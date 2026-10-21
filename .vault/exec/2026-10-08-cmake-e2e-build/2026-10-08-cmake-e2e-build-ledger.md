---
tags:
  - '#exec'
  - '#cmake-e2e-build'
date: '2026-10-08'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:de7be156f89e2ea479d76717b3f81565921a7c00efcb1297743db4028309c6bc'
related:
  - "[[2026-10-08-cmake-e2e-build-plan]]"
---

# `cmake-e2e-build` ledger

## Changes

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
- `S01` `verify:` `cmake snapshot release desktop-headless-test with bundled documentation` -> `fail`
- `S01` `verify:` `cmake snapshot release bundle with CADRUMO_PACKAGE_USER_DOCS=OFF` -> `pass`
- `S01` `verify:` `ctest snapshot release -R bundle (5 tests)` -> `pass`
- `S01` `verify:` `cmake standalone desktop-windows-x64-release desktop-headless-test` -> `pass`
- `S01` `verify:` `cmake standalone desktop-windows-x64-release desktop-run` -> `pass`
- `S01` `verify:` `python -m dev.quality.types (live checkout)` -> `fail`
- `S01` `M` `dev/docs/compile_once.py`
- `S01` `M` `dev/docs/pagefind_index.py`
- `S01` `M` `dev/docs/tests/test_pagefind_index.py`
- `S01` `M` `dev/packaging/native/tests/test_docs_build_environment.py`
- `S01` `M` `native/cmake/ReleaseVerification.cmake`
- `S01` `verify:` `cmake user_docs_driver_test (44 unit and integration tests)` -> `pass`
- `S01` `verify:` `python -m dev.quality.types` -> `pass`
- `S01` `verify:` `ruff check .` -> `pass`
- `S01` `verify:` `ruff format --check changed files` -> `pass`
- `S01` `verify:` `ruff format --check .` -> `fail`
- `S01` `verify:` `import loadability and subordinate checker` -> `pass`
- `S01` `verify:` `run_import_linter using CMake-managed executable (15 contracts)` -> `pass`
- `S01` `verify:` `app-distro first separated build: documentation round-trip line endings` -> `fail`
- `S01` `verify:` `cmake snapshot release app-distro (desktop, runtime and four-language documentation)` -> `pass`
- `S01` `verify:` `ctest snapshot release bundle with package-root override unset (6 tests)` -> `pass`
- `S01` `verify:` `cmake -E env packaged cadrumo.exe from Y:/ with package-root override unset: version, help, no arguments` -> `pass`
- `S02` `M` `native/application/src/child.rs`
- `S02` `M` `native/cmake/Packaging.cmake`
- `S02` `A` `dev/packaging/native/package_launch_smoke.py`
- `S02` `M` `native/CONTRACT.md`
- `S02` `verify:` `ctest release application.rust (111 tests)` -> `pass`
- `S02` `verify:` `cmake release verify-app-distro (8 tests including full inventory and CMD launch)` -> `pass`
- `S02` `verify:` `CMake CMD packaged no-argument launch from <user-home> without overrides` -> `pass`
- `S02` `verify:` `ruff check .` -> `pass`
- `S02` `verify:` `python -m dev.quality.types` -> `pass`
- `S02` `verify:` `changed Python and Rust formatting; git diff --check` -> `pass`
- `S02` `verify:` `ruff format --check .` -> `fail`

## Notes

- `S01` S01 remains open. Full page check passed; desktop-headless-test is running and waiting for the shared docs cache held by windows-installers-x64. No executable acceptance yet.
- `S01` User explicitly requested package assembly after the Session 0 launch reported a missing package. Shared-cache reuse is OFF for this preset; all validation remains enabled. The active desktop-headless-test build is executing documentation checks before bundle assembly and Session 0 acceptance.
- `S01` Runtime-only bundle and standalone executable launch succeeded. Full desktop distribution remains blocked by documentation runtime deadline and shutdown failures. No session-number branch was added; existing desktop availability checks govern launch mode. S01 remains open for full distribution acceptance.
- `S01` User explicitly separates app-distro, ZIP and release verification. Corrected search stamping to preserve line endings; rebuild pending. Full format check reports unrelated application/overview/calendar.py drift. Initial import graph command lacked managed tool PATH; reran that component successfully with its absolute managed executable, preserving passing loadability/checker evidence.
- `S01` Complete non-zipped distribution exists at build/windows-x64/product/build/source/build/windows-x64/stage/Release/app. Packaged CADRUMO 0.5.1 exits 0 for version/help/no-argument launch. Session 0 permits headless execution only; no production session-selection code changed. ZIP and full live release verification remain separate and were not run for this user-requested distribution.
- `S02` Unrelated calendar.py formatting remains. First build refused concurrent documentation input changes; final retry passed. Initial CMD unit fixture was replaced with a native child environment assertion; real CMD package acceptance passed. GUI interaction unavailable in Session 0; no production selection logic changed.
