---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-07-17'
body_hash: 'sha256:37051fdf99d6e6088433d3f81a26ca67619e9243f2cff4fc2a6f6aa994f4adce'
step_id: 'S06'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

# vaultspec-high-executor: collapse the three near-identical observation-folding loops onto the one fold helper from the phase-2.2 resolver contract, preserving the M130 direct-carry and M353 per_grupo_member output shapes exactly (apply-cached on collision, peer-WIP likely)

## Scope

- `src/aeat/application/calculations/_relation_prefill.py`

## Description

- Extract the byte-identical relation observation-fold logic, duplicated as `_observed_requirement_values` in both the application relation prefill and the domain relations module, into one shared helper module `_observation_fold.py` in the domain registry package.
- Expose `gather_observed_requirement_values` (match one observed filing per source period, extract the source casilla), `fold_observed_requirement_values` (copy/sum to one Decimal), and `resolve_observed_requirement_value` (gather plus fold), re-exported through the registry package facade.
- Delete the application twin's `_resolve_requirement_value` and its local gather in favour of `resolve_observed_requirement_value`; delete the domain twin's local gather in favour of `gather_observed_requirement_values`, keeping its two-stage `resolve_relation_values` fold so the public domain contract and its validation stay byte-identical.
- Scaffold the API docs stub for the new module.

## Outcome

- One commit `a52f1317e` (`relocation:observation-fold-helper`), 6 files. No casilla value shifts: the gather and fold are byte-for-byte the prior logic, now single-sourced. The full registry plus calculations suites passed (3253 tests, unchanged baseline); the relation-fold and pull-vs-calculate parity surfaces passed (125 tests); collect-only clean.

## Notes

- The reference named the application source mesh as the helper home; that is architecturally impossible for the domain twin (domain cannot import application). The domain registry package is the boundary-correct home, and the fold is pure domain logic. Recorded as an autonomous architecture correction, not a value-affecting choice.
- The shared error text adopts the more informative domain form (carrying the relation ids); no test pins the prior application-path text.
