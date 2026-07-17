---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

# vaultspec-standard-executor: type RelationDefinition.aggregation as the BindingAggregation plus BindingAggregationOp model, hydrating the registry op token at the loader boundary (report-before-land, abort-on-WIP)

## Scope

- `src/aeat/domain/calculations/registry/_relations.py`

## Description

- Add the new core `RelationAggregationOp` StrEnum (copy/sum) and the `RelationAggregation` model in `core/aggregation.py`, mirroring `BindingAggregation` with the same string-to-member `_coerce_op` hydration.
- Type `RelationDefinition.aggregation` to `RelationAggregation | None` at `_schema_surfaces.py`; the loader's `ModeloRevision.model_validate` hydrates the TOML mapping into the typed model.
- Bump the registry tree cache schema version so the on-disk registry pickle, keyed on the TOML fingerprint, invalidates for a Python schema-shape change.

## Outcome

- Landed in the single atomic P01 commit `4b3311a02` (`relocation:RelationAggregationOp`). The typed field hydrates end-to-end; an isolated round-trip and the committed-registry build both produce the typed `RelationAggregation`.

## Notes

- The plan named `_relations.py` as the field's home; the field is actually declared in `_schema_surfaces.py` (per reference drift D2), so the typing edit landed there.
- Per the D3 ADR amendment, a NEW `RelationAggregationOp` enum is used, not a reuse of phase-2.1's `BindingAggregationOp` (the two op axes are deliberately separate).
- Root-caused a stale on-disk registry pickle that deserialised the pre-typing dict shape under the new typed field; the cache-version bump is the intended invalidation mechanism.
