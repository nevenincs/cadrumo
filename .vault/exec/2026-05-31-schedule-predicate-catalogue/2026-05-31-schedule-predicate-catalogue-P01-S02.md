---
tags:
  - '#exec'
  - '#schedule-predicate-catalogue'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S02'
related:
  - "[[2026-05-31-schedule-predicate-catalogue-plan]]"
---

# `schedule-predicate-catalogue` `P01.S02`

Added inline comments to the two hardcoded attribute aliases in
`_resolve_profile_fact` inside `_schedules.py` (lines 81-90 after edit).

- Modified: `src/aeat/domain/calculations/registry/_schedules.py`

## Description

Each alias block now carries a comment explaining the schema predicate path
it serves (`iva.regime` → `TaxpayerProfile.iva_regime`, `taxpayer.entity_type`
→ `TaxpayerProfile.entity_type`) and why the alias exists (dotted TOML path
vs. flat Python attribute name). No behavioural change.

## Tests

- `test_filing_schedule_selection.py`: 4 passed, 0 failed
- Commit: 513c3c75d
