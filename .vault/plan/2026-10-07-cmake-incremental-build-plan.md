---
tags:
  - '#plan'
  - '#cmake-incremental-build'
date: '2026-10-07'
tier: L1
related:
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:a44f58f868fceef2a4cc45b84c6f10b54ca584085334e11fb0233af26da815f3'
---

# `cmake-incremental-build` plan

## Description

Approved 2026-10-07

The user explicitly authorized fixing all seven CMake review findings and establishing fingerprints and stable incremental outputs. The accepted interpreter foundation's CMake amendment governs build, install, ZIP and cleanup ownership. These are implementation corrections within that decision. Preserve concurrent source edits. Source discovery uses direct reads because the semantic service is unavailable.


Approved follow-up 2026-10-07: the user selected missing-only authority compilation for ordinary builds, explicit CMake republication on request, and reuse of existing local publications without compiler/source freshness checks. S05 implements this selection consistently through CMake and the wheel hook. Existing publication validation and independent registry currency checks remain. The accepted authority boundary's legal-only identity and explicit compiler republication policy apply; no artifact format or runtime identity change is introduced.

## Steps

- [x] `S01` - Make desktop builds content-stable and complete standalone prerequisites; `native/desktop CMake targets, scripts and dedicated build tests`.
- [x] `S02` - Narrow native action fingerprints and preserve unchanged generated outputs with separate binary targets; `native CMake targets and packaging helpers assigned in Parallelization`.
- [x] `S03` - Complete CMake prerequisite ownership, per-target cleanup and install-based ZIP packaging; `root CMake, shared packaging and cleanup helpers, justfile`.
- [ ] `S04` - Verify integrated incremental builds and final ZIP and document supported commands; `native/CONTRACT.md, build verification and review audit`.
- [x] `S05` - Reuse existing authority publications and compile only when missing or explicitly requested; `native authority CMake helper and targets, authority wheel hook, focused tests and workflow documentation`.

## Parallelization

S01 desktop targets, scripts and dedicated tests and S02 native fingerprints and stable generation may execute concurrently with S03 prerequisite orchestration, packaging and cleanup. Desktop worker owns native/desktop/CMakeLists.txt, scripts and dedicated build tests. Fingerprint worker owns native/CMakeLists.txt, native platform/application targets, PackageInputs.cmake, Contract.cmake, Authority.cmake, authority_build.py, cmake_build.py, metadata.py, generation/provision helpers and dedicated tests. Cleanup worker owns Cleanup.cmake, Bootstrap.cmake, cleanup.py, distribution preparation and dedicated tests. Supervisor owns remaining shared CMake integration, justfile, documentation, vault and commits. Specific follow-up assignments transfer bounded ownership; shared metadata writes stay serialized. S04 follows all three. Shared expensive builds have one supervisor owner.

## Verification

Exercise real CMake targets in isolated fixtures and the configured native build. Check unchanged reruns preserve output hashes and mtimes, content changes invalidate affected actions, deleted outputs recover, independent targets have complete prerequisites, and target-specific clean preserves sibling outputs. Validate install/CPack ZIP and executable permissions. Run scoped format/lint/types/tests, then build and verify the full application ZIP where host prerequisites permit. Record exact limitations; historical archives are not current verification. Completion requires closed Steps and a passing integrated review.
