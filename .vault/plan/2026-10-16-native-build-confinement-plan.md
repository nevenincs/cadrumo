---
tags:
  - '#plan'
  - '#native-build-confinement'
date: '2026-10-16'
tier: L1
related:
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
modified: '2026-10-16'
body_schema: body-v2
body_hash: 'sha256:0ee9e697983e0b5dae38d7b51e63a5a0a9af00f0f049181b29d07ba11376b01d'
---

# `native-build-confinement` plan

## Description

Approved 2026-10-16

The current user instruction authorizes a complete native build writer audit and fixes removing custom uv cache/environment management and writes outside canonical build targets. The accepted interpreter-foundation decision supplies CMake ownership and build/<preset> output placement. This applies those constraints to existing tooling; no new runtime storage or installation policy is introduced. Concurrent native-build-incremental edits remain owned by their originating session.

## Steps

- [ ] `S01` - Remove repository-managed uv and tool environment provisioning; `justfile, uv tool-path declarations and samples/workflows, docs build defaults, conftest.py, src/cadrumo/conftest.py, dev/test_runs, related Python packaging/release build destinations and owner-aware cleanup, release workflow cohort paths, packaging/authority/hatch_build.py and covering tests`.
- [ ] `S02` - Confine native documentation and verification scratch and prevent source dependency installation during builds; `dev/packaging/native writer CLIs, build_directory.py, docs and verification helpers, CMake root and native/cmake, native/desktop frontend prerequisites and build/test wrappers, native/CONTRACT.md, build skill references and covering tests`.

## Parallelization

S01 and S02 may run concurrently. Luna max agent audit_uv owns S01 tool declarations, justfile and covering bootstrap tests. Within S02, audit_cmake owns frontend prerequisite validation and binary-directory link admission; audit_writes owns verification helpers and their CMake arguments; the parent owns documentation, authority input validation, writer census, all vault metadata and integrated checks. Write scopes are disjoint. Preserve concurrent Bootstrap, BuildPaths, cmake_build and producer incrementality edits.


## Verification

Run focused Python tests, Ruff lint and format checks, configured type checks and Node frontend install/path tests. Verify native builds validate externally provisioned dependencies and authority without installing into sources, and documentation/verification outputs remain build-owned. Persist the writer classification and final integrated review. Do not claim a native bundle rebuild without executing it.
