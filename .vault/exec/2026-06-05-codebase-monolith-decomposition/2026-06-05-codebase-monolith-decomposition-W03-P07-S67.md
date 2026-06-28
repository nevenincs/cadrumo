---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S67'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S67 Registry Record Design Decomposition

Scope: `src/aeat/domain/calculations/registry/_record_design.py src/aeat/domain/calculations/registry/*.py`.

## Description

- Extract record-design parser output models from `_record_design.py` into `_record_design_schema.py`.
- Keep `_record_design.py` importing and re-exporting `RecordDesignField` and `RecordDesignSheet` for existing registry imports.
- Preserve package-top-level registry facade identity for `RecordDesignField` and `RecordDesignSheet`.

## Outcome

The record-design parser and coverage module no longer owns its pydantic output model definitions directly. The model surface now has a focused private schema module while the existing `_record_design.py` and package facade imports remain stable.

## Notes

No consumer-facing import path changed. No behavior skips, fakes, mocks, monkeypatches, or xfails were introduced.
