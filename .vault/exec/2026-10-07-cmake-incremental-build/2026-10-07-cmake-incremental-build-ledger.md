---
tags:
  - '#exec'
  - '#cmake-incremental-build'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:587dbc401a05eff52e3d5ae0ea5110967d799a7e7212f16311eead42e1ab72eb'
related:
  - "[[2026-10-07-cmake-incremental-build-plan]]"
---

# `cmake-incremental-build` ledger

## Changes

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
- `S04` `M` `native/CONTRACT.md`
- `S04` `A` `.vault/audit/2026-10-07-cmake-incremental-build-audit.md`
- `S04` `verify:` `just check-style` -> `pass`
- `S04` `verify:` `just check-format` -> `pass`
- `S04` `verify:` `just check-types` -> `fail`
- `S04` `verify:` `scoped ty check changed Python files after corrections` -> `pass`
- `S04` `verify:` `actual native unchanged-build artifact timestamp comparison` -> `pass`
- `S01` `verify:` `node --test native/desktop/tests/content-build.test.mjs native/desktop/tests/backend-snapshot.test.mjs native/desktop/tests/frontend-clean.test.mjs native/desktop/tests/frontend-install.test.mjs` -> `pass`
- `S05` `M` `dev/packaging/native/authority_build.py`
- `S05` `M` `dev/packaging/native/tests/test_authority_build_fingerprints.py`
- `S05` `M` `native/cmake/Authority.cmake`
- `S05` `M` `packaging/authority/hatch_build.py`
- `S05` `M` `dev/packaging/tests/test_authority_build_hook.py`
- `S05` `M` `justfile`
- `S05` `M` `native/CONTRACT.md`
- `S05` `verify:` `pytest native authority helper and authority build hook tests (18 tests)` -> `pass`
- `S05` `verify:` `cmake --preset windows-x64` -> `pass`
- `S05` `verify:` `cmake --build build/windows-x64 --config Release --target registry_authority` -> `pass`
- `S05` `verify:` `scoped Ruff format lint and ty for four changed Python files` -> `pass`
- `S05` `verify:` `just check-style` -> `pass`
- `S05` `verify:` `just check-format` -> `fail`
- `S05` `verify:` `just check-types` -> `fail`

## Notes

- `S02` Authority compiler fingerprint remains intentionally conservative in its canonical owner; this does not establish minimal compiler invalidation.
- `S03` Full application ZIP acceptance is assigned to S04 and remains pending behind the foreign documentation build; real install/CPack fixtures pass.
- `S04` S04 remains open. Full application package attempt was stopped while queued behind an already-running foreign documentation build; package-release and verify-package must be completed when that shared output is available.
- `S04` Repository type check reported two concurrent registry schema private-usage diagnostics; five in-scope diagnostics were fixed and scoped ty now passes. No unrelated source edits reverted.
- `S01` Exact 23-test worker invocation includes frontend-install.test.mjs; the earlier verification row listed only three of its four test files.
- `S05` Global formatting failure is concurrent `test_native_installation.py` drift; global type failure is concurrent application/operations/registry.py pyrefly diagnostic. Scoped modified files pass. Full publication was not rerun against shared authority; existing publisher command is unchanged.
