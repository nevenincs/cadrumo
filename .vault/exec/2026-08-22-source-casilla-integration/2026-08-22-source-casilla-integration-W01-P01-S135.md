---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:33d3368967bb5996514ae02f6e852ee747c31bbf1b700602f237b2d957ab8ac9'
step_id: 'S135'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# replace the configurable proof fake with real authority and encrypted-revision mutation coverage

## Scope

- `src/cadrumo/application/registry/tests/test_source_connectivity_authority.py`

## Description

- Compose `LiveSourceConnectivityProofAuthority` from canonical route ownership, actual reconciled CLI inventory, encrypted revision storage, and descriptor-safe evidence verification.
- Persist and reload exact primary provenance through the financial secure-object repository.
- Refuse connection, workflow, evidence, source-disposition, revision, primary-identity, fingerprint, and ambiguity mutations.
- Delete a required lineage axis from the stored catalogue payload and prove encrypted rehydration fails closed.
- Confirm the remaining core authority double is only a protocol unit probe, not a configurable production proof path.

## Outcome

Connected census rows are admitted only by real route ownership, real CLI reachability, unchanged repository evidence, and one exact encrypted primary. The integration suite passes 15 tests.

## Notes

The initial review found composite provenance conflation, a hand-built workflow leaf, and insufficient raw-payload mutation proof. The accepted ADR amendment plus S149-S155 resolved every finding. The formal review audit records the corrections and verification.
