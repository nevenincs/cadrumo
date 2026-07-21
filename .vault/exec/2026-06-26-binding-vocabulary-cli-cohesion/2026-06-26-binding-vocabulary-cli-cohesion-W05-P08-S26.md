---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S26'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# DEFERRED FOLLOW-UP (paired with the selector union): narrow the typed_enum stringly-typed pointer (str-or-None enum class name) on DataBindingDefinition to a typed enum-class reference, sweeping the bindings list CLI table, the ModeloBindingQueryRow projection, the borrador resolver, and the Sheets-pull router

## Scope

- `gated by test_schema_hygiene.py`
- `atomic commit with docs-scaffold + API-stub + docstring-core-struct regen`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/domain/calculations/registry/_schema.py`
- `src/aeat/domain/calculations/registry/_queries.py`

## Description

Commit `071438bd6`. Replaced the raw string `typed_enum` pointer on
`DataBindingDefinition` with the closed `BindingTypedEnumKind` member at the
schema boundary, preserving string-valued public projections for query and CLI
consumers.

## Outcome

W05.P08.S26 implementation complete. Registry TOML tokens hydrate to
`BindingTypedEnumKind`; unknown tokens fail at construction, while
`ModeloBindingQueryRow` and other operator-facing projections remain
byte-compatible through StrEnum value serialization.

## Notes

Verification is tracked separately by S27. A focused S27 run on 2026-07-02 failed
because `test_selector_shape.py` already contains non-authored WIP and is behind
the committed `DONATIVO_DONOR` selector registry entry; this record documents only
the landed S26 implementation.
