---
tags:
  - '#plan'
  - '#registry-drift-validator-blocking-gap'
date: '2026-06-04'
modified: '2026-06-04'
tier: L1
related:
  - '[[2026-06-04-registry-drift-validator-blocking-gap-adr]]'
  - '[[2026-06-04-registry-drift-validator-blocking-gap-research]]'
  - '[[2026-06-04-registry-remaining-hardening-wireframe-audit]]'
  - '[[2026-06-04-registry-generic-fragmentation-contract-audit]]'
  - '[[2026-06-04-registry-generic-fragmentation-contract-code-review-audit]]'
---

# `registry-drift-validator-blocking-gap` `implementation` plan

Identify whether any registry drift validator still reports an advisory result
where the registry load should fail, and close one narrowly scoped blocking
gap with real regression coverage.

## Description

The remaining-hardening wireframe names drift validators as the next substrate
after generic fragment support. This plan does not authorize schema semantics
changes or legal registry edits. It authorizes an audit-first pass over the
validator surface and one focused blocking conversion only when the audit
selects a concrete gap.

## Steps

- [x] `S01` - Audit advisory and hard-fail registry drift validators and select one blocking-gap candidate; `.vault/audit`.
- [x] `S02` - Add a focused regression that proves the selected drift gap is not currently blocked; `src/aeat/domain/calculations/registry`.
- [x] `S03` - Convert the selected drift gap into a `RegistryValidationError` without changing unrelated validator semantics; `src/aeat/domain/calculations/registry`.
- [x] `S04` - Verify drift, committed-registry, loader, reviewability, and plan gates; `src/aeat/domain/calculations/registry`.
- [x] `S05` - Review and close the drift-validator blocking-gap slice; `.vault/audit`.
## Parallelization

S01 must land first. S02 and S03 are ordered because the regression must prove
the gap before production validator behavior changes. S04 and S05 close the
slice after implementation.

## Verification

The plan is complete when every Step is closed and these checks pass:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-registry-drift-validator-blocking-gap-plan.md`
