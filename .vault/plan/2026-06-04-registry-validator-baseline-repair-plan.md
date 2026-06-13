---
tags:
  - '#plan'
  - '#registry-validator-baseline-repair'
date: '2026-06-04'
modified: '2026-06-04'
tier: L1
related:
  - '[[2026-06-04-registry-validator-baseline-repair-adr]]'
  - '[[2026-06-04-registry-validator-baseline-repair-research]]'
  - '[[2026-06-04-registry-validator-baseline-audit]]'
  - '[[2026-06-04-registry-row-width-pressure-plan]]'
---


# `registry-validator-baseline-repair` `implementation` plan

Repair the dirty validator-module line-count regression that blocks the
registry reviewability gate without raising module baselines.

- [x] `S01` - Compress `_validate_relation_periods.py` docstrings without changing validator semantics; `src/aeat/domain/calculations/registry/_validate_relation_periods.py`.
- [x] `S02` - Verify registry reviewability and row-width plan gates after the validator baseline repair; `src/aeat/domain/calculations/registry`.
- [x] `S03` - Review and close the validator-baseline repair slice; `.vault/audit`.
## Description

The row-width pressure plan is open at final verification because
`test_registry_reviewability.py` fails on `_validate_relation_periods.py` at
217 lines against its 203-line baseline. The scoped diff is documentation-only.
This plan preserves the documentation intent in a shorter form, keeps validator
semantics untouched, and leaves the existing baseline in place.

## Steps

## Parallelization

S01 must land before S02. S03 follows verification.

## Verification

The plan is complete when every Step is closed and these checks pass:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-registry-validator-baseline-repair-plan.md`
