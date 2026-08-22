---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:ac60c0c8a9e9ba0ff4f1756d25bd215aa01be8057bcadb8196edde120def426d'
step_id: 'S03'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# define the connected-slice proof contract for resolver ownership, revision persistence, and operator reachability

## Scope

- `src/cadrumo/core/source_connectivity.py`

## Description

- Ground connected proof against live resolver, encrypted revision, and CLI workflow evidence patterns.
- Define typed resolver ownership proof with canonical source kind, stable resolver identity, owner, and enrollment evidence.
- Define encrypted revision proof requiring strict round trip, at-rest encryption, anti-tautology mutation, and typed evidence.
- Define operator reachability proof with stable entrypoint identity, supported command, observed resolver, and typed evidence.
- Aggregate all three proof families and refuse missing proof on connected rows or proof on non-connected rows.

## Outcome

A `connected` census claim now requires one complete
`SourceConnectivityConnectedProof`. Its three mandatory typed components prove
resolver ownership, encrypted calculation-revision persistence, and operator
reachability. Non-connected dispositions cannot carry connected proof, so stale
or anticipatory attestations fail closed.

## Notes

Ruff and module compilation passed. Focused runtime assertions admitted a fully
proved connected row, refused a connected row without proof, refused proof on a
non-connected row, and refused an encrypted-revision proof whose at-rest claim
was false. This contract records typed evidence locators but does not dereference
HTTPS URLs. The S02 review's HTTPS trust-policy finding remains relevant to any
future automated fetcher and is not silently widened by this step.
