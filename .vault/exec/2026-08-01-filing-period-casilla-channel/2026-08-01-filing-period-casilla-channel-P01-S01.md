---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:d9cdc9b316575391e7ef7cb8241042441a530780654808649f51fbd8fbd7d301'
step_id: 'S01'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Verify working-tree ownership of the uncommitted typed-scalar routing set with the owning campaign and adopt it unchanged rather than re-authoring it

## Scope

- `src/cadrumo/application/filing/__init__.py`

## Description

- Sample the uncommitted typed-scalar routing set's diffstat repeatedly and confirm it is byte-identical before touching it.
- Adopt every file in the set unchanged; author no replacement for any of it.
- Record the set's true extent, which is wider than the dispatch brief described.

## Outcome

No owning campaign was identified. The working-tree change had no reachable author and no teammate claimed it. The ownership half of this Step's action therefore did NOT happen as written; it was satisfied by the coordinator-authorised substitute of repeated stability sampling. This is recorded rather than glossed because the action text says "with the owning campaign".

The diffstat was sampled three times - at 14:14:10, 14:14:32 and 14:24:59 - and was identical across all three, every file at the same insertion and deletion counts. Combined with a prior eight-minute observation reported in the dispatch brief, that is roughly eleven minutes of stability with no live editor.

The set is 22 files, wider than the three packages the brief named. It spans `src/cadrumo/application/filing/` (three production modules plus four test modules), `src/cadrumo/domain/calculations/registry/` (eight production modules plus four test modules) and `src/cadrumo/domain/filing/` (two protocol and validator modules).

Adopted with zero edits to any adopted production line. The single additive touch sits inside `src/cadrumo/application/filing/tests/test_text_casilla_routing.py`, where the S08 build-gate test was added and two constants of identical value were folded into one.

## Notes

The second stability sample was taken 22 seconds after the first, not the 60 seconds the dispatch required. The third sample, at a ten-minute remove, supplies the required interval; samples one and two do not.

Independent proof that adoption stayed faithful: after each of the two S08 mutation experiments the diffstat for `src/cadrumo/application/filing/__init__.py` returned to 34 changed lines, identical to its pre-adoption value. The adopted set was restored byte-for-byte both times.
