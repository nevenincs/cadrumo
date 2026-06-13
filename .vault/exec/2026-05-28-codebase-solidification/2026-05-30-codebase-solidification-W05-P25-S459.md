---
step_id: S459
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W05.P25.S459

## Step

Migrate `"ledger_transaction"` bare default at `ledger/_actions.py:3143` and `_bindings.py:1629,1648` + `_schema.py:1787` to `AggregationSourceKind.LEDGER_TRANSACTION`.

## Outcome

- `_actions.py`: Added `from ...core.aggregation import AggregationSourceKind` import; replaced `"source_kind": "ledger_transaction"` with `AggregationSourceKind.LEDGER_TRANSACTION`.
- `_bindings.py`: Added `from ....core.aggregation import AggregationSourceKind` and `cast` import; changed `Field(default="ledger_transaction")` to `Field(default=cast(CounterpartSourceKind, AggregationSourceKind.LEDGER_TRANSACTION))`. The `Literal` type alias and `COUNTERPART_BINDING_SOURCE_KINDS` frozenset string members remain as Literal strings — they are type-annotation boundaries that cannot take enum members.
- `_schema.py:1787`: The `Literal[..., "ledger_transaction", ...]` union in `DataBindingDefinition.source` is a Pydantic type annotation boundary; it must remain as a string literal. No change made — the StrEnum value satisfies the Literal constraint at runtime.
- Pyright type safety preserved via `cast(CounterpartSourceKind, ...)`.

## Files touched

- `src/aeat/application/ledger/_actions.py`
- `src/aeat/domain/calculations/registry/_bindings.py`
