---
step_id: S42
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W05.P14.S42 — ModeloCapability rename to ModeloFilingCapability (RENAME-002)

## Files modified

- `src/aeat/domain/calculations/registry/_schema.py` — renamed `ModeloCapability` declaration and both internal usages (`capabilities` field annotation, `has_capability` method parameter)
- `src/aeat/domain/calculations/registry/__init__.py` — updated import and `__all__` entry

## Commit

`a8e8009fb` — refactor(registry): rename ModeloCapability to ModeloFilingCapability (RENAME-002 W05.P14.S42)

## Before / After

- Before: `ModeloCapability = Literal["borrador", "renta_ledger_default"]`
- After: `ModeloFilingCapability = Literal["borrador", "renta_ledger_default"]`

No callers outside the registry package. Zero consumers of the old name found post-rename.

## Test run

```
python -c "from aeat.domain.calculations.registry import ModeloFilingCapability; print(ModeloFilingCapability)"
# → typing.Literal['borrador', 'renta_ledger_default']
```
