---
tags:
  - '#exec'
  - '#application-packaging'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:af34f1e127ad50b770ad626d335389022a727bd486286049f8c1406590cb4bee'
related:
  - "[[2026-10-03-application-packaging-plan]]"
---

# `application-packaging` ledger

## Changes

- `S01` `A` `native/CONTRACT.md`
- `S01` `A` `native/package-layout.json`
- `S01` `A` `.vault/adr/2026-10-03-application-packaging-interpreter-foundation-adr.md`
- `S01` `M` `.vault/adr/2026-10-03-application-packaging-adr.md`
- `S01` `M` `.vault/research/2026-10-03-application-packaging-research.md`
- `S01` `verify:` `canonical ownership and Windows Linux macOS mapping review` -> `pass`
- `S02` `A` `native/toolchain.json`
- `S02` `A` `native/CMakeLists.txt`
- `S02` `A` `native/platform/Cargo.toml`
- `S02` `A` `native/platform/Cargo.lock`
- `S02` `A` `native/platform/include/cadrumo_platform.h`
- `S02` `A` `native/platform/src/lib.rs`
- `S02` `A` `native/platform/src/consumer.rs`
- `S02` `A` `native/platform/tests/consumer.c`
- `S02` `A` `dev/packaging/native/__init__.py`
- `S02` `A` `dev/packaging/native/generate.py`
- `S02` `A` `dev/packaging/native/provision.py`
- `S02` `verify:` `MSVC SDK Rust pinned native build and C static DLL Rust consumers` -> `pass`
- `S02` `verify:` `fresh official SDK SHA256 and 77 locked Windows dependency wheels` -> `pass`
- `S02` `A` `native/interpreter/host.c`
- `S02` `A` `native/interpreter/python.c`
- `S03` `A` `native/interpreter/bootstrap.py`
- `S03` `A` `dev/packaging/native/assemble.py`
- `S03` `A` `dev/packaging/native/product.py`
- `S03` `verify:` `fresh product wheel build and package assembly` -> `pass`
- `S03` `verify:` `ruff check format and ty native Python tooling` -> `pass`
- `S04` `A` `dev/packaging/native/verify.py`
- `S04` `A` `dev/packaging/native/trace_analysis.py`
- `S04` `A` `dev/packaging/native/filesystem.wprp`
- `S04` `M` `native/CONTRACT.md`
- `S04` `A` `.vault/audit/2026-10-03-application-packaging-audit.md`
- `S04` `M` `.vault/research/2026-10-03-application-packaging-research.md`
- `S04` `M` `.vault/adr/2026-10-03-application-packaging-interpreter-foundation-adr.md`
- `S04` `verify:` `fresh relocated product verifier hostile inputs package hashes` -> `pass`
- `S04` `verify:` `trace.ps1 repeatable-trace 2013 events 4 writes zero events lost` -> `pass`
- `S04` `verify:` `integrated corrective native review` -> `pass`
- `S05` `M` `dev/packaging/native/artifact_verify.py`
- `S05` `M` `native/tests/package_smoke.py`
- `S05` `verify:` `ctest --preset release (four tests)` -> `pass`
- `S05` `verify:` `pytest native storage environment contract (two tests)` -> `pass`
- `S05` `verify:` `ruff check and format dev/packaging/native native/tests` -> `pass`
- `S05` `verify:` `ty check --python-platform win32 dev/packaging/native native/tests` -> `pass`
- `S05` `verify:` `artifact_verify Release archive be4eaf81eb2b254d2d535db69609efbe684bca9c790d0994609268fb39923b0b` -> `pass`
- `S05` `verify:` `fresh outside-checkout Release install manifest equality and --check-package` -> `pass`
- `S04` `verify:` `fresh final Release installation ETW: 71288 scoped events, four writes, zero lost events` -> `pass`
- `S04` `verify:` `installed manifest equals accepted Release manifest ce36b6a5d59f8ab0df72c5be26a41fdc4f0a611f2a8e50222b887e6d1ad63b7d` -> `pass`
- `S05` `M` `.gitignore`
- `S05` `M` `dev/packaging/native/assemble.py`
- `S05` `D` `dev/packaging/native/build.ps1`
- `S05` `D` `dev/packaging/native/filesystem.wprp`
- `S05` `M` `dev/packaging/native/generate.py`
- `S05` `M` `dev/packaging/native/product.py`
- `S05` `M` `dev/packaging/native/provision.py`
- `S05` `D` `dev/packaging/native/trace.ps1`
- `S05` `M` `dev/packaging/native/trace_analysis.py`
- `S05` `M` `dev/packaging/native/verify.py`
- `S05` `M` `native/CMakeLists.txt`
- `S05` `M` `native/CONTRACT.md`
- `S05` `M` `native/interpreter/bootstrap.py`
- `S05` `D` `native/interpreter/host.c`
- `S05` `D` `native/interpreter/python.c`
- `S05` `M` `native/package-layout.json`
- `S05` `M` `native/platform/Cargo.toml`
- `S05` `M` `native/platform/src/lib.rs`
- `S05` `M` `native/toolchain.json`
- `S05` `A` `CMakeLists.txt`
- `S05` `A` `CMakePresets.json`
- `S05` `A` `dev/packaging/native/action_cache.py`
- `S05` `A` `dev/packaging/native/artifact_verify.py`
- `S05` `A` `dev/packaging/native/cleanup.py`
- `S05` `A` `dev/packaging/native/cmake_build.py`
- `S05` `A` `dev/packaging/native/hashing.py`
- `S05` `A` `dev/packaging/native/layout.py`
- `S05` `A` `dev/packaging/native/metadata.py`
- `S05` `A` `dev/packaging/native/platforms/__init__.py`
- `S05` `A` `dev/packaging/native/platforms/pe.py`
- `S05` `A` `dev/packaging/native/platforms/windows-filesystem.wprp`
- `S05` `A` `dev/packaging/native/platforms/windows.py`
- `S05` `A` `dev/packaging/native/platforms/windows_trace.ps1`
- `S05` `A` `dev/packaging/native/platforms/windows_trace_analysis.py`
- `S05` `A` `dev/packaging/native/platforms/windows_verify.py`
- `S05` `A` `dev/packaging/native/stdlib.py`
- `S05` `A` `dev/packaging/tests/test_native_artifact_identity.py`
- `S05` `A` `native/cmake/Artifact.cmake.in`
- `S05` `A` `native/cmake/CPackProject.cmake.in`
- `S05` `A` `native/cmake/Packaging.cmake`
- `S05` `A` `native/cmake/WindowsToolchain.cmake`
- `S05` `A` `native/cmake/platforms/Windows.cmake`
- `S05` `A` `native/interpreter/windows/bootstrap.py`
- `S05` `A` `native/interpreter/windows/host.c`
- `S05` `A` `native/interpreter/windows/host.manifest`
- `S05` `A` `native/interpreter/windows/python.c`
- `S05` `A` `native/platforms/windows-x64.json`
- `S05` `A` `native/tests/package_smoke.py`
- `S05` `A` `native/tests/windows_smoke.py`
- `S05` `verify:` `CPack Debug and Release creation plus unchanged locators after reconfigure` -> `pass`
- `S05` `verify:` `archive replacement regression and storage contracts: three tests` -> `pass`
- `S05` `verify:` `source snapshot includes authored Windows manifest` -> `pass`
- `S05` `M` `.vault/audit/2026-10-03-application-packaging-audit.md`
- `S05` `verify:` `final CPack Debug and Release full ZIP acceptance with hash-bound locators` -> `pass`
- `S05` `verify:` `final installed package smoke from unrelated cwd: 119 native identities and 80 distributions` -> `pass`
- `S05` `verify:` `final integrated Windows foundation review` -> `pass`

## Notes

- `S04` Verified artifact and scoped ETW proof pass for preserved native snapshot. Concurrent native policy edits invalidate current-source approval; S02 and S03 reopened and S04 remains open pending policy reconciliation and rebuild.
- `S05` Recovered the interrupted S02-S05 shared CMake graph as one cohesive checkpoint; separate native/application work is excluded.
