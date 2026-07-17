---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S349'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# R9-ANDREA-CONTEXT registry caching observed to break under concurrent file writes

## Scope

- `closed by 688ed6713: registry loader cache hardening moved the invalidation model to directory-aware fingerprinting and added directory-mode regression coverage for concurrent-write-style cache churn`
- `this addresses the stale/singular timestamp failure mode Andrea observed while peer agents were writing registry TOML fragments in the shared worktree`
- `src/aeat/domain/calculations/registry/_loader.py`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `688ed67133` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
