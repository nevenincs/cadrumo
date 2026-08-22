---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:5aca86088f5314c1eeddca04384f342bcacc0cd59be96dd1a5983997d0bd0dcd'
step_id: 'S143'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# derive live proof enrollment and exact workflow reachability from canonical calculation-route ownership

## Scope

- `src/cadrumo/application/registry`

## Description

- Replace public free-form resolver enrollment with an exact projection of the
  canonical production calculation route and source dispositions.
- Represent resolver-owned sources and the sole manual-input pseudo-owner with
  separate strict typed models.
- Require operator proofs to carry the canonical route and CLI path.
- Join one exact reviewed workflow to one exact route source owner and the complete
  source connection before authorizing reachability.
- Refuse partial, invented, renamed, deferred, reserved, wrong-route, wrong-path,
  wrong-command, wrong-resolver, wrong-source, and missing-live-leaf claims.
- Preserve encrypted revision matching as the separate exact persisted provenance
  join.

## Outcome

Connected workflow authority no longer trusts caller-authored enrollment rows or a
Cartesian conjunction of independent facts. Ownership is projected from the live
production route, workflow identity is canonically coherent at model construction,
and authorization joins the full relational identity.

## Notes

Focused integration coverage passed: 94 tests. Ruff, compilation, import hygiene,
obsolete-API census, and diff checks passed. Independent review found one high
workflow-constructor cross-pair; it was corrected and re-review passed with no
remaining findings. Concurrent unrelated work was neither modified nor staged.
