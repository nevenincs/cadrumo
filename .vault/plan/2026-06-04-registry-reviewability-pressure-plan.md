---
tags:
  - '#plan'
  - '#registry-reviewability-pressure'
date: '2026-06-04'
modified: '2026-06-04'
tier: L2
related:
  - '[[2026-06-04-registry-generic-fragmentation-contract-audit]]'
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-05-20-registry-authority-flow-adr]]'
  - '[[2026-05-20-registry-authority-flow-research]]'
  - '[[2026-06-04-registry-reviewability-pressure-adr]]'
  - '[[2026-06-04-registry-reviewability-pressure-research]]'
---


# `registry-reviewability-pressure` `implementation` plan

Audit and reduce the remaining registry TOML reviewability pressure after the
generic fragmentation contract was verified.

### Phase `P01` - pressure inventory

Classify the near-threshold committed TOML files and inline-only revision
directories before any registry layout change.

- [x] `P01.S01` - Audit near-threshold TOML line and row pressure for M123, M369, M100, M200, and M303; `.vault/audit`.
- [x] `P01.S02` - Decide whether M123 and M369 inline-only revision directories need mechanical fragment splits now or tracked deferral; `.vault/audit`.

### Phase `P02` - mechanical reviewability repairs

Apply only audit-authorised layout changes that preserve schema semantics and
loaded `ModeloDefinition` objects.

- [x] `P02.S03` - Split M123 inline-only revision directories into reviewable revision fragments if S02 authorises it; `src/aeat/_data/registry/aeat/modelos/123`.
- [x] `P02.S04` - Split M369 inline-only revision directories into reviewable revision fragments if S02 authorises it; `src/aeat/_data/registry/aeat/modelos/369`.
- [x] `P02.S05` - Tighten reviewability regression gates only after corpus pressure headroom is improved; `src/aeat/domain/calculations/registry/test_registry_reviewability.py`.

### Phase `P03` - verification and closure

Verify the reviewability-pressure slice through real loader and registry gates,
then persist code review.

- [x] `P03.S06` - Verify loader equivalence, reviewability, committed registry, record-design, drift, and plan gates for reviewability repairs; `src/aeat/domain/calculations/registry`.
- [x] `P03.S07` - Review the reviewability-pressure slice and persist closure artefacts; `.vault/audit`.

## Description

The previous registry hardening wave proved fragmentation support is generic
and identified the next reviewability risks: M123 has the largest remaining
TOML file near the baseline line-count cap, M100 has the widest observed row
near the baseline row-width cap, and M123/M369 still contain revision
directories whose complete revision content lives in `revision.toml`. This plan
keeps the work audit-first and mechanical. It does not authorise schema
semantics changes, modelo-specific loader branches, or legal-definition edits.

## Steps

## Parallelization

P01 must land before any registry data layout edit. If S02 authorises both
splits, S03 and S04 can run independently because they touch different modelo
directories. S05 follows any split work so the gate is tightened against the
post-repair corpus. P03 closes the plan after all implementation steps.

## Verification

The plan is complete when every Step is closed and these checks pass:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_record_design.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-registry-reviewability-pressure-plan.md`
