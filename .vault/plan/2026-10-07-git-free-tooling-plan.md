---
tags:
  - '#plan'
  - '#git-free-tooling'
date: '2026-10-07'
tier: L1
related:
  - '[[2026-10-07-git-free-tooling-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:20b496117be7c3cce5224665da2559301eef76029b33b504c39422c3755f27dc'
---

# `git-free-tooling` plan

## Description

Approved 2026-10-07

The user's explicit prohibition authorizes removing every repository-owned Git CLI invocation and Git-calling test. The accepted git-free-tooling decision governs all Steps. Prior CI lane and native identity obligations remain; their local Git acquisition mechanisms are replaced. This is an L1 sequence covering developer tooling, builds, packaging and workflow shells.

## Steps

- [x] `S01` - Remove Git dependencies and Git-specific tests from local tooling and native build metadata; `dev/env, dev/registry/edition_round_trip.py, dev/deploy/docs_delivery_policy.py, native/cmake/BuildNumber.cmake, dev/packaging/native/tests/test_cmake_build_number.py`.
- [x] `S02` - Replace Git calls in CI selection and release packaging with explicit inputs and forge APIs; `dev/ci, dev/packaging/smoke_homebrew.py, dev/packaging/smoke_scoop.ps1, justfile, .github/workflows`.
- [x] `S03` - Enforce zero Git CLI calls and verify audit coverage and integrated behavior; `dev/quality/tests, .vault/audit, .vaultspec/rules`.

## Parallelization

Execute sequentially in the shared worktree. Preserve all concurrent edits; stage only owned changes.

## Verification

Run focused unit and integration tests for changed owners, configured scoped lint, formatting, type checking and data-file quality. Prove the executable-call gate detects Python, native and workflow violations and finds zero current calls. Re-run the dead-code audit and report signal and any pre-existing failures separately. Release/package-manager execution on unavailable hosts remains explicitly unverified; do not publish remotely.
