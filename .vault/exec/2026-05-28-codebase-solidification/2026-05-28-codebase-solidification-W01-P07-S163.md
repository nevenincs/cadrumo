---
step_id: S163
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P07.S163 — AggregationSourceKind bare-string migration

## Outcome

Migrated 19 raw source-kind string literals to `AggregationSourceKind` enum members
across 5 application-layer files. The `AggregationSourceKind` enum was already defined
in `_source_kinds.py`; `_service.py` already imported from there. A circular import
was avoided by importing directly from `._source_kinds` in the three modules that
`_service.py` imports (`_counterpart`, `_retenciones`, `_foreign_assets`).

Domain files (`_bindings.py`, `_schema.py`) were left unchanged: their `Literal`
annotations are the canonical TOML wire-protocol schema definitions — the application
enum's `.value` strings derive from them, not the reverse. Importing from application
layer into domain would violate architecture boundaries.

## Files touched

| File | Sites migrated | Change |
| --- | --- | --- |
| `src/aeat/application/aggregation/_counterpart.py` | 4 | `_CANONICAL_SOURCE_KINDS` frozenset |
| `src/aeat/application/aggregation/_retenciones.py` | 4 | `_CANONICAL_SOURCE_KINDS` tuple |
| `src/aeat/application/aggregation/_foreign_assets.py` | 4 | `_CANONICAL_SOURCE_KINDS` frozenset |
| `src/aeat/application/aggregation/_registry_provider.py` | 4 | `_COUNTERPART_BINDING_SOURCE_KINDS` frozenset |
| `src/aeat/application/review/_operator.py` | 7 | dict keys (4) + assignment sites (3) |

## Deferred files

- `src/aeat/domain/calculations/registry/_bindings.py` — domain cannot import from application; `Literal` annotations + frozensets are the canonical wire-protocol source
- `src/aeat/domain/calculations/registry/_schema.py` — `DataBindingDefinition.source` `Literal` is the TOML schema definition
- `src/aeat/application/modelo/_actions.py` — grep confirmed zero matches; no sites to migrate

## Collision check

`git diff` on all 8 target files returned no output before edits. Clean workspace confirmed.

## Test result

414 tests pass across `src/aeat/application/aggregation/` and `src/aeat/application/review/`.
Pre-existing failure in `test_committed_registry_tree_has_required_model_law_coverage`
(models 036 + 390 `executable_parity_evidence` coverage gaps) unrelated to this step.

## Commit

`c6ce46de2` — `aggregation(S163+S164): migrate AggregationSourceKind bare strings to enum members`
