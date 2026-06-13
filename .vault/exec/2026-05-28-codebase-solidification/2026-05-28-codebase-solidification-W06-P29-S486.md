---
step_id: S486
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P29.S486

**Step**: migrate ledger_transaction bare sites in _bindings.py:1631,1637,2846 + _schema.py:1787 to AggregationSourceKind.LEDGER_TRANSACTION.

## Outcome

Migrated all bare `"ledger_transaction"` runtime sites in `_bindings.py` and `_schema.py`:
- `_bindings.py`: CounterpartSourceKind Literal arms, COUNTERPART_BINDING_SOURCE_KINDS frozenset, _BINDING_SELECTOR_REGISTRY dict key — all now use `AggregationSourceKind.LEDGER_TRANSACTION`
- `_schema.py`: DataBindingDefinition.source Literal annotation — imported AggregationSourceKind and replaced the bare string
- Sibling discovery: CounterpartSourceKind Literal (line 1629-1635) also migrated to enum members

## Files

- `src/aeat/domain/calculations/registry/_bindings.py`
- `src/aeat/domain/calculations/registry/_schema.py`

## Commit

5b45dd58c
