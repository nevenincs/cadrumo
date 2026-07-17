---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S42'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Draft the dirty-set mutation contract research if write latency remains material

## Scope

- `.vault/research/2026-07-06-ledger-perf-optimization-research.md`

## Description

- Load the `vaultspec-research` workflow and research template.
- Search ADRs for an existing dirty-set decision and confirm only the read-path latency ADR exists for this feature.
- Search code for dirty-set mutation, transaction repository save, and single-row ledger writer surfaces.
- Read the transaction repository, secure-object batch write boundary, common ledger save helper, manual update paths, and bulk classify save-once path.
- Append dirty-set mutation contract research to the existing feature research artifact.

## Outcome
- `.vault/research/2026-07-06-ledger-perf-optimization-research.md` now contains the W05.P14.S42 dirty-set mutation contract research.
- The research records current contract sources, three design options, required invariants, and the recommendation to draft an additive dirty-set repository write ADR.
- The recommended ADR scope preserves the current full reconciliation fallback, bucket isolation, derived date-index rebuildability, unchanged-row revision stability, and secure-object atomic co-writes.

## Notes

- `fd` did not find a local `vaultspec-adr-researcher` persona file in the worktree, so the main agent followed the research workflow directly.
- `uv run vaultspec-core status` confirmed this feature is still active and S42 was the next open step.
- No runtime code changed in this step.
