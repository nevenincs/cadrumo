---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S25'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# Replace DataBindingDefinition.selector with the BindingSourceKind selector union

## Scope

- `lands only if the rename pass is light or as a separate phase): replace the free-form DataBindingDefinition.selector BindingSelectorMap Mapping with a discriminated union keyed by BindingSourceKind so the per-family selector models in _bindings.py BECOME the schema rather than a validate-time overlay`
- `updating the _schema.py field and alias`
- `the _schema_scalars.py alias`
- `and the _validate_binding_selector_shapes snapshot gate`
- `atomic commit with docs-scaffold + API-stub + docstring-core-struct regen`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP. NOTE: H3 source_revision_selector on the relation surface is NOT the binding selector and is out of scope`
- `src/aeat/domain/calculations/registry/_schema.py`
- `src/aeat/domain/calculations/registry/_schema_scalars.py`
- `src/aeat/domain/calculations/registry/_bindings.py`

## Description

Commit `071438bd6`. Promoted `DataBindingDefinition.selector` from a free-form
mapping to a hydrated selector model selected by the `BindingSourceKind` dispatch
table. Added the construction-time selector validation path, retained the
snapshot-build op/fact invariants, and kept the relation `source_revision_selector`
surface out of scope.

## Outcome

W05.P08.S25 implementation complete. The schema now stores per-family selector
models through `BindingSelector`, with `_BINDING_SELECTOR_REGISTRY` and
`selector_model_for_source` as the typed dispatch authority.

## Notes

Verification is tracked separately by S27. A focused S27 run on 2026-07-02 failed
because `test_selector_shape.py` already contains non-authored WIP and is behind
the committed `DONATIVO_DONOR` selector registry entry; this record documents only
the landed S25 implementation.
