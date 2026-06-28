---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S09'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---




# bind the recargo casillas, update the M303 manifest and construct, and add a real-behavior test that a recargo supplier's recargo cuota aggregates instead of reporting zero

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/`

## Description

Bound the M303 recargo cuota casillas and closed the recargo silent zero.

- Set casillas 158 (0.5%), 21 (1.4%), 24 (5.2%) to `input_kind = bound` with their
  recargo binding and added `ley-37-1992:art-161` to each casilla's legal_refs.
- Added the three casillas to the M303 completeness manifest and the three
  bindings + three casillas to the construct in `revision.toml`, with art-161 added
  to the construct legal_refs so the three-layer coverage check holds.
- Updated the M303 calculate test binding-value maps (registry, compensacion-carry,
  special-case routing) to supply the new recargo bindings.

Files under
`src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/` (casillas,
completeness_manifest, revision.toml) plus the affected test binding maps.

## Outcome

The registry loads with the recargo binds; the M303 recargo casillas leave the
manifest-drift closure-only set (only the peer's 01/04/07/28 base-binding drift
remains). The full registry+aggregation+ledger sweep: 3745 passed, the only two
reds being pre-existing peer-owned gates (M303 base manifest drift; a peer
iva-wallet tautology test). The recargo cuotas now aggregate instead of reporting
zero.

## Notes

The M303 casilla files carried stale (~35h) uncommitted peer base-binding work in a
different region; the recargo edits were made additively without disturbing the
peer's casilla 01/04/07/28 changes, and nothing was committed.
