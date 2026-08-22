---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:02d83c591e306410532854cd85ca13e71d0cd9c368717fb01a4659fd916f87fe'
step_id: 'S141'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# bind operator workflow authority validation to the full source connection identity

## Scope

- `src/cadrumo/core`

## Description

- Replace independent workflow identity arguments with the complete connection and
  typed operator-reachability proof at the core authority seam.
- Pass both relational objects from connected-row validation without changing the
  separate enrollment and encrypted-revision checks.
- Migrate the live application authority and deterministic test authority without a
  compatibility method.
- Prove stale one-argument implementations fail during protocol use and cross-source
  workflow proofs can be refused.
- Exercise the application implementation with real typed proof and catalogue models.

## Outcome

An operator workflow can no longer be authorized independently of the resolver,
source reference, source kind, candidate, and persisted calculation revision it is
claimed to reach. The old method is absent tree-wide, and core remains independent
of application packages and ambient I/O.

## Notes

Focused core and registry contract tests passed: 52. Ruff, compilation, import
hygiene, and diff checks passed. Independent review found one low test-fixture issue;
it was corrected with real typed models and sent for re-review. Concurrent unrelated
working-tree changes were left untouched and unstaged.
