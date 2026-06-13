---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S13'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Author the ten single-leaf projection FormulaDefinition blocks (modelo-303-dr303-NN-projection for boxes 09/06/03/11/13/27/29/33/37/45) in revision.toml, each with target the box id, an expression that is the one semantic casilla-id leaf, money-2 rounding, and the box legal_refs

## Scope

- `register each id in the revision formula list`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`

## Description

- Author the ten single-leaf projection FormulaDefinition blocks (modelo-303-dr303-NN-projection for 09/06/03/11/13/27/29/33/37/45) in the formulas/0001-dr303-projections.toml fragment (moved out of revision.toml to stay under the reviewability baseline).
- Each: target the box id, expression the one semantic casilla-id leaf, money-2 rounding, box legal_refs verbatim, boe source citation.
- Register each id in the revision formulas list.

## Outcome

- Step landed; focused gates green (registry M303 load, verification-substance operator parity, the M303 official-box projection suite).

## Notes

- The DSL-operator edits touch `_schema.py` and `_verification_actions.py`, which carried concurrent peer WIP (a DT-12 advisory extraction). The edits are additive and in disjoint regions; the working tree is internally consistent and all focused tests pass.
