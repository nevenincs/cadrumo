---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:78358091fa14a91c6d02d90625f567883e8eb4374eeac218a258e2af3c980632'
step_id: 'S01'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# define the closed connectivity disposition taxonomy and candidate identity model

## Scope

- `src/cadrumo/core/source_connectivity.py`

## Description

- Ground the contract against the accepted ADR, research, plan, and existing census identity patterns.
- Define the exact eight-member `SourceConnectivityDisposition` vocabulary.
- Define a constrained `SourceConnectivityCandidateId` token and immutable `SourceConnectivityCandidateIdentity` model.
- Keep source locators, proposed destinations, evidence, ownership, expiry, and connected proof outside stable identity.
- Run Ruff, module compilation, and an import-level contract assertion over the complete disposition set.

## Outcome

`src/cadrumo/core/source_connectivity.py` now provides a strict, frozen,
location-independent candidate identity and the closed disposition taxonomy
authorized by the ADR. The model deliberately leaves the S02 and S03 contract
fields unimplemented.

## Notes

`uv run --no-sync ruff check src/cadrumo/core/source_connectivity.py` passed.
`uv run --no-sync python -m compileall -q src/cadrumo/core/source_connectivity.py`
passed. The import-level assertion instantiated `inventory.stock` and proved the
enum value set exactly matches the eight ADR dispositions. A direct Pyright run
could not start because the `pyright` executable is not installed in the current
environment; no type-check failure was suppressed.
