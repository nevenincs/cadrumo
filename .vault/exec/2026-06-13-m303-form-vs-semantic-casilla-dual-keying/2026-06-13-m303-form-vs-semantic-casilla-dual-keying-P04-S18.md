---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S18'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Narrow the deducible implies_any_nonzero advisory predicate to drop populated constituents (29/33 and 37 if wired) and keep it firing only for any box left manual (e.g. 37 if deferred)

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/verification_expectations/0001-verification_predicates.toml`

## Description

- Retire the deducible implies_any_nonzero advisory predicate: ALL its constituents (29/33/37) are now computed projections (box 37 wired to AIC-deducible, not deferred).
- The calculate-path advisory reads these same predicates, so retiring them narrows the calculate advisory in lock-step.

## Outcome

- Step landed; focused gates green (registry M303 load, verification-substance operator parity, the M303 official-box projection suite).

## Notes

- The DSL-operator edits touch `_schema.py` and `_verification_actions.py`, which carried concurrent peer WIP (a DT-12 advisory extraction). The edits are additive and in disjoint regions; the working tree is internally consistent and all focused tests pass.
