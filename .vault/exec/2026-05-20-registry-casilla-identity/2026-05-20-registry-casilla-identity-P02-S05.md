---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S05'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P02.S05`

Defined segment-aware casilla reference resolution in the registry
validator.

- Modified: `src/aeat/domain/calculations/registry/_validate.py`

## Description

The registry validator previously resolved every casilla reference —
formula `casilla` leaves and `target`, export field `casilla`, relation
`source_output`, algorithm binding inputs and outputs, extraction
profile `target_casillas`, verification expectation `computed_casillas`
— against `casillas = set(casilla_by_id)`, a flat set of casilla `id`
values. Because every authored casilla fragment sets `id == number`,
that resolved bare numbers only as a side effect of the convention.

A new module-level helper `_resolvable_casilla_references` builds the
segment-aware resolvable token set. A reference resolves when it is
either a declared casilla `id`, or a bare `number` that occurs on
exactly one casilla across the whole revision — so the segment is
unambiguous and the bare number resolves within its segment context. A
bare `number` that recurs across distinct record segments is excluded:
such a reference must use the segment-qualified `id` to name the
intended occurrence, so only genuinely cross-segment numbers carry that
cost. `_validate_revision` now builds `casillas` from this helper rather
than from `set(casilla_by_id)`.

Correctness for single-segment modelos is exact. Every casilla in the
~25 single-segment modelos sets `id == number` with `segmento` unset
and every number is unique within the revision, so the resolvable set
is identically the set of casilla ids — byte-identical to the prior
`set(casilla_by_id)`. Every formula, export, relation, algorithm
binding, and extraction profile reference resolves precisely as before.

## Tests

`uv run --no-sync pytest` on `test_schema_hygiene.py`,
`test_referential_integrity.py`, `test_modelo_parity_coverage.py`: 39
passed, 1 failed (the pre-existing P01.S03
`test_registry_tests_do_not_define_schema_authority_objects` failure,
unrelated to and untouched by this Step). `test_modelo_200_registry.py`,
`test_modelo_100_registry.py`, `test_modelo_303_registry.py`: 54
passed — formula, export, and algorithm-binding reference resolution
exercised across single-segment modelos with zero regression. All 26
modelos load valid. `ruff check` on `_validate.py` clean.
