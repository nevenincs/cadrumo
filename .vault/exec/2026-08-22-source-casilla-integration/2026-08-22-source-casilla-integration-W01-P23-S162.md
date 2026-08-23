---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:3a8ed0386efa733882246fed3921370cb58e8d3ad6dd437a6830fa4ae4f0e52f'
step_id: 'S162'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# extend ingress discovery across canonical command-spec declarations and adjudicate the resulting census drift

## Scope

- `dev/source_connectivity/discovery.py`

## Description

- Discover canonical `CommandSpec` write leaves alongside legacy Typer decorators.
- Preserve stable handler identities while locating evidence at the active command declaration.
- Derive write-policy membership structurally from local-state policy declarations.
- Support keyword and positional command-spec constructors, including local `_leaf` factories.
- Re-adjudicate every newly visible profile and configuration transport before refreshing the frozen remainder.

## Outcome

The ratchet rejected an apparent ingress reduction during the concurrent command-spec migration. The extended sentinel now classifies 103 ingress surfaces and 448 total capabilities, including positional profile command declarations, without treating configuration transports as independent tax source facts. The focused source-connectivity suite passes with 20 tests.

## Notes

The first keyword-only parser still missed positional `CommandSpec` declarations. A second drift failure exposed that blind spot before the census digest was accepted; positional constructor coverage was then added and mutation-tested.
