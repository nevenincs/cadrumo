---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S04'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P02.S04`

Generalised the casilla duplicate-id invariant to `(segmento, number)`
uniqueness per modelo revision.

- Modified: `src/aeat/domain/calculations/registry/_validate.py`

## Description

The registry validator previously enforced casilla uniqueness only
through the table-driven per-kind `id` duplicate check
(`_emit_per_kind_duplicate_failures`). Because every authored casilla
fragment sets `id == number`, that check effectively forbade duplicate
bare numbers, but only as a side effect of the `id == number`
convention.

A new module-level helper `_emit_casilla_identity_failures` keys
uniqueness on the pair `(segmento, number)`. It is invoked from
`_validate_revision` immediately after the existing per-kind and
combined-primary-id duplicate checks. The `id` per-kind check is left in
place: `id` remains the stable within-revision handle per the ADR and
must stay unique; the new check adds the segment-scoped identity
invariant alongside it.

Correctness for single-segment modelos is exact. Every casilla in the
~25 single-segment modelos leaves `segmento` unset (`None`), so the
identity pair degrades to `(None, number)`. A `(None, number)`
collision — two casillas sharing a number with no segment — is reported
with the message `duplicate casilla number '<number>'`, hard-failing
the load precisely as the prior duplicate-id check did. A
segment-qualified collision reports
`duplicate casilla number '<number>' within segmento '<segmento>'`.
Detection order is deterministic (first repeat reported once, sorted by
`(segmento or "", number)`), so single-segment validation output is
byte-identical to before for any modelo with no duplicate numbers.

## Tests

`uv run --no-sync pytest` on `test_schema_hygiene.py`,
`test_referential_integrity.py`, and `test_modelo_parity_coverage.py`:
39 passed, 1 failed. The single failure
(`test_registry_tests_do_not_define_schema_authority_objects`) is
pre-existing — it flags that the P01.S03 test module constructs
`CasillaDefinition`, introduced by commit `1706b30a2`, and is unrelated
to and untouched by this Step. All 26 modelos load valid:
`test_modelo_parity_coverage` and the committed-registry referential
integrity gate both pass. `ruff check` on `_validate.py` clean.
