---
step_id: S164
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P07.S164 — StrEnum surface coverage tests

## Outcome

Added 8 real-behavior tests to `src/aeat/application/aggregation/test_service.py`
asserting that every migrated source-kind constant uses `AggregationSourceKind` members
rather than raw strings.

## Tests added

| Test | Assertion |
| --- | --- |
| `test_accepted_source_kinds_are_enum_members` | Every entry in `ACCEPTED_SOURCE_KINDS` is `isinstance(kind, AggregationSourceKind)` |
| `test_accepted_source_kinds_covers_all_four_members` | `frozenset(ACCEPTED_SOURCE_KINDS) == frozenset(AggregationSourceKind)` |
| `test_counterpart_canonical_source_kinds_are_enum_members` | `_counterpart._CANONICAL_SOURCE_KINDS` entries are enum members |
| `test_retenciones_canonical_source_kinds_are_enum_members` | `_retenciones._CANONICAL_SOURCE_KINDS` entries are enum members |
| `test_foreign_assets_canonical_source_kinds_are_enum_members` | `_foreign_assets._CANONICAL_SOURCE_KINDS` entries are enum members |
| `test_registry_provider_counterpart_binding_source_kinds_are_enum_members` | `_registry_provider._COUNTERPART_BINDING_SOURCE_KINDS` entries are enum members |
| `test_operator_accepted_kind_map_uses_enum_keys_for_aggregation_source_kinds` | Four aggregation kind keys in `_ACCEPTED_KIND_TO_INTERNAL` are `AggregationSourceKind` instances |
| `test_aggregation_source_kind_values_are_stable` | Enum `.value` strings remain backwards-compatible with AEAT vocabulary |

Anti-tautology rationale: `isinstance(kind, AggregationSourceKind)` fails if a raw `str`
is present; raw strings are `str` subclass but not `AggregationSourceKind` instances.
The value-stability test asserts against AEAT-specified string vocabulary, not computed outputs.

## Test result

20/20 tests pass in `test_service.py`. 414 tests pass across aggregation + review.

## Commit

`c6ce46de2` — `aggregation(S163+S164): migrate AggregationSourceKind bare strings to enum members`
