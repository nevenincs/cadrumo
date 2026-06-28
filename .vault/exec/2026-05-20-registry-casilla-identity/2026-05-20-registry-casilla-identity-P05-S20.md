---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S20'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P05.S20`

Added a strict roundtrip test for the extended `CasillaDefinition` that
populates the additive `segmento` field with a non-default value, pushes
it through the registry's real on-disk load transform, and asserts strict
pydantic equality across the boundary.

- Modified: `src/aeat/domain/calculations/registry/test_referential_integrity.py`

## Description

`test_segmented_casilla_survives_strict_load_cycle_roundtrip` builds a
fully-populated multi-segment `CasillaDefinition` — every defaultable
field set to a non-default value, including `segmento = "DP200014"`,
`semantic_role`, `semantic_role_cardinality`, `export_refs`, and
multi-entry `legal_refs` / `source_refs` — then pushes it through the
genuine load cycle the registry loader applies to every fragment:
`model_dump(mode="python")` to the fragment payload shape, `freeze_toml`
(the exact normalisation `_merge_revision_fragment` applies to every TOML
fragment it reads), then `model_validate` back across the
strict / frozen / `extra="forbid"` boundary. The test asserts
`round_tripped == casilla` (strict pydantic equality) and that
`segmento` survives at its non-default `DP200014` value.

Populating the defaultable fields with non-default values is the
roundtrip-discipline requirement: a save-drops-field /
load-re-defaults-field regression on `segmento` is invisible if the
fixture leaves it at the `None` default. The pre-existing
`test_single_segment_casilla_validates_unchanged_with_segmento_unset`
covers the unset path; this Step closes the populated-`segmento` gap.

The test is sited in `test_referential_integrity.py`, which is already a
member of the `test_schema_hygiene.py` `_VALIDATOR_TEST_ALLOWLIST`, so
constructing a `CasillaDefinition` directly does not trip the
schema-hygiene gate. The `freeze_toml` loader primitive was added to the
module import block.

## Tests

`pytest test_referential_integrity.py test_schema_hygiene.py` — the new
roundtrip test passes; `ruff check` on the touched file is clean.

Collision note: `test_schema_hygiene.py` carries a concurrent
uncommitted change by another agent that generalises
`test_no_duplicate_casilla_numbers_within_a_revision` from `number`
uniqueness to `(segmento, number)` identity uniqueness — the correct
adaptation to the P04 multi-segment M200 casillas. That file is another
agent's work and is not staged or committed by this Step.
