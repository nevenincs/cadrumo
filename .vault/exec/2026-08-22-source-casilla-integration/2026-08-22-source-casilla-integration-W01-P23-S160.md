---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:f196aa1d5f89e473751ed29bc964b2eea9495df4c532fc0fde614ba766a585c6'
step_id: 'S160'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# decide and implement the canonical live connected-proof gate composition

## Scope

- `src/cadrumo/application/registry`

## Description

- Compose connected census checks from the canonical live authority, production ownership and workflow catalogues, and repository-root digest verification.
- Execute independently authored typed invoice inputs through canonical invoice construction and persistence, enrolled source resolution, registry calculation, atomic revision persistence, and encrypted reload.
- Keep the zero-connected census path free of fixture, storage, and key allocation.
- Prove source mutation changes both revision identity and primary fingerprint, missing primary identity fails closed, and ephemeral storage is removed on exit.

## Outcome

The canonical connected-proof composition now has one data-only fixture boundary and one composer-owned encrypted calculation lifecycle. Census assertions cannot author the expected workflow, destination, provenance, or stored revision, and the live authority adjudicates all axes conjunctively.

## Notes

Formal re-review passed with no Critical, High, or Medium findings. Six focused live-proof tests pass after the invoice-ingress and cleanup tightening; Ruff and the focused `ty` surface pass. A broader full-authority run was temporarily blocked after successful calculation persistence by unrelated concurrent operator-surface reconciliation work, and an intermediate collection was blocked by an unrelated concurrent `SCHEMA_REGISTRY` migration. Both shared-worktree conditions were outside S160 and were not repaired here.
