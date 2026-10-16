---
tags:
  - '#plan'
  - '#native-build-incremental'
date: '2026-10-16'
tier: L1
related:
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
  - '[[2026-10-16-native-build-disk-audit-reference]]'
  - '[[2026-10-16-native-build-incremental-adr]]'
modified: '2026-10-16'
body_schema: body-v2
body_hash: 'sha256:64cd14320446d1bbe02cb50d388655d06fa0dff7178ce944f3e357be3df70abf'
---

# `native-build-incremental` plan

## Description

Approved 2026-10-16

The user explicitly authorized fixing repeated copying and packaging, forbade build-created environments and writes to `_deps` or `var`, required deleting var uv caches after commit/push, and requested delegated installer review with only one MSI compilation. The incremental build decision governs S01-S05; the interpreter foundation governs runtime/SDK isolation. Existing distribution/maintenance decisions retain scope, authentication, rollback and version lifetime protections. The audit reference supplies grounded producer and disk evidence.

## Steps

- [x] `S01` - Use existing developer tools and confine build writes to enrolled binary directories; `dev/_paths.py, native/cmake/Bootstrap.cmake, native/cmake/BuildPaths.cmake, dev/packaging/native/cmake_build.py and build storage tests`.
- [x] `S02` - Reuse unchanged wheel and agent runtime producers; `dev/packaging/native/product.py, agent.py, agent_runtime.py and tests`.
- [x] `S03` - Publish assembly incrementally without erasing the previous application; `dev/packaging/native/assemble.py, assembly helpers and tests, native/desktop/tests/packaged/host.mjs`.
- [x] `S04` - Compile one MSI with incremental ownership and verified native installation lifecycle; `native/cmake/distribution, dev/packaging/native/windows_msi*.py, native/installer, native/application/src/installation/maintenance and tests`.
- [ ] `S05` - Verify Debug and Release incremental packages, review installer, publish fixes and remove var uv caches; `native build verification, focused tests, .vault audit and execution ledger, var uv caches`.

## Parallelization

S01 is owned by the parent. Python producer S02 and assembly S03 workers may run concurrently with S01 in disjoint files; the parent owns their shared cmake_build integration. The installer worker owns S04, including native maintenance observation, runner and MSI/CMake tests. S05 integrates all steps after their focused checks; an independent worker reviews installer changes before completion. Parent owns vault records, shared verification and commits. No worker may revert concurrent work.

## Verification

Existing developer interpreter selection and cleanup tests pass without creating environments. Machine uv settings survive imports and just recipes. Base dependency and wheel/agent no-op tests preserve unchanged member timestamps and rebuild only changed inputs. Assembly rollback/tamper tests and desktop snapshot tests pass. CMake Debug and Release app-payload builds pass and repeated builds preserve output bytes. Installer compiled invocation count is at most one per changed payload and zero unchanged; scope, role-qualified ownership, candidate rollback, removal and authentication tests pass. Review must identify any unavailable native runner evidence. Commit/push precedes removing all var uv caches; final inventory checks no such caches remain.
