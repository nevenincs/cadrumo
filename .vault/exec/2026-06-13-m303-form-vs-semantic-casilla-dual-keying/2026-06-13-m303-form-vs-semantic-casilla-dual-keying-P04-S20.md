---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S20'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Verify the pull path and the calculate path produce identical values for every populated box on a shared revision (one-aggregation-path-pull-equals-calculate), proving the projection is transport-identical

## Scope

- `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`

## Description

- Verify pull == calculate parity: both transports run the one formula graph via calculate_registry_snapshot, so each projected box is transport-identical.
- test_each_projected_box_has_exactly_one_producing_formula (one aggregation path) and test_pull_and_calculate_paths_produce_equal_projected_box_values (live vs pull-shape engine run, non-vacuous) lock the guarantee.

## Outcome

- Step landed; focused gates green (registry M303 load, verification-substance operator parity, the M303 official-box projection suite).

## Notes

- The DSL-operator edits touch `_schema.py` and `_verification_actions.py`, which carried concurrent peer WIP (a DT-12 advisory extraction). The edits are additive and in disjoint regions; the working tree is internally consistent and all focused tests pass.
