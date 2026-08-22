---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:7580e6fc0b0506361eb6bdacd835bb35584bd7440585c47d08a872d05587b504'
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
- Bind every proof and executable evidence record to one shared candidate, source kind, source object, resolver, and revision identity.
- Replace prose command claims with constrained entrypoint and command identities.
- Require strict boolean truth assertions that reject numeric or textual substitutes.

## Outcome

A `connected` census claim now requires one relational
`SourceConnectivityConnectedProof`. Its resolver, encrypted-revision, operator,
and executable-evidence components must all name the same candidate, canonical
source kind, source object, resolver, and calculation revision. The census row
must name that same candidate. Non-connected dispositions cannot carry connected
proof, so stale, mismatched, deferred-source, or anticipatory attestations fail
closed.

## Notes

Ruff and module compilation passed. Focused runtime assertions admitted a fully
proved connected row, refused a connected row without proof, refused proof on a
non-connected row, and refused an encrypted-revision proof whose at-rest claim
was false. This contract records typed evidence locators but does not dereference
HTTPS URLs. The S02 review's HTTPS trust-policy finding remains relevant to any
future automated fetcher and is not silently widened by this step.

Corrective probes also refused cross-component source-object drift, executable
evidence tied to an unrelated connection, a census-row candidate mismatch, and
integer `1` in every strict proof-boolean field. Executable connected evidence
must use a stable repository locator naming a test module; implementation-only
and external grounding cannot attest runtime behavior. The census row docstring
now describes the landed relational proof contract.
