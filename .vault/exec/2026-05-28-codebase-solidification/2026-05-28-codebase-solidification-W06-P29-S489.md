---
step_id: S489
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P29.S489

**Step**: add INVOICE member to AggregationSourceKind and migrate 4 bare 'invoice' sites.

## Outcome

- Added `INVOICE = "invoice"` to `AggregationSourceKind` in `aeat.core.aggregation`
- `_bindings.py`: Literal arms in CounterpartSourceKind + frozenset + dict key + guard comparison all use `AggregationSourceKind.INVOICE`
- `_schema.py`: DataBindingDefinition.source Literal arm uses `AggregationSourceKind.INVOICE`
- `_validate_record_sections.py`: source_validators tuple uses `AggregationSourceKind.INVOICE`
- Sibling discovery: `_retenciones.py:81` comparison `value == "invoice"` migrated

## Files

- `src/aeat/core/aggregation.py`
- `src/aeat/domain/calculations/registry/_bindings.py`
- `src/aeat/domain/calculations/registry/_schema.py`
- `src/aeat/domain/calculations/registry/_validate_record_sections.py`
- `src/aeat/application/aggregation/_retenciones.py` (sibling)

## Commit

5b45dd58c
