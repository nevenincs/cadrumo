---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:717fbb01eef1d311f20eab092ded328ed91cadba3a5357e500fc7f5091981db9'
step_id: 'S10'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [L | opus-medium] Build the materialiser between raw fragment assembly and typed construction, producing the same merged mapping typed construction already consumes. The construction signature and everything above it are untouched. Proof: consumers observe no change on an unmigrated corpus.

## Scope

- `src/cadrumo/domain/calculations/registry/_loader_internals.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/_loader_internals.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_edition_materialisation.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_revision_predecessor_declaration.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_revision_edition_materialisation.py src/cadrumo/domain/calculations/registry/tests/test_revision_predecessor_declaration.py src/cadrumo/domain/calculations/registry/tests/test_revision_predecessor_forest.py` -> `pass`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`

## Notes

- The fixture in `test_revision_predecessor_declaration.py` repeated a casilla without `continuidad_id` in both editions while declaring a predecessor, and the materialiser refuses that as a collision with no lineage key. The fixture casilla now carries one lineage in both editions.
- Three registry tests fail both with and without this change: `test_legal_parameters_only_preserves_valid_parameter_key_identity`, `test_modelo_309_2004_country_role_mutation_reopens_typed_semantic_drift` and `test_both_occupancy_directions_have_a_positive_case_in_the_corpus`.
- The reviewer persona could not be launched from this session, so the review is still outstanding.

- The reviewer persona could not be launched; the orchestrating session reviewed the S10 and S35 diffs together against the ADR. Only a named predecessor edge triggers inheritance, casillas are the only family that inherits (the manifest is excluded explicitly), the forest check runs before recursion, and each merge ambiguity is refused naming both sides. Verification: 99 tests passed across materialisation, forest, declaration, placement, 369, minimality and totality; `registry verify` exit 0; ruff and ty clean. Inherited rows still carry predecessor-edition tokens until restatement is lifted.
