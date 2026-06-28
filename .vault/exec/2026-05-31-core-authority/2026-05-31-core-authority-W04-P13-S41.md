---
step_id: S41
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

# core-authority W04.P13.S41 — ModeloActorLabel rename (MERGE-015)

## Files modified

Four files in `src/aeat/domain/modelos/`, each renamed `_ActorLabel` to `ModeloActorLabel` and updated field annotations:

- `_calculation_revision.py` — `verified_by`, `filed_by`, `discarded_by` fields
- `_filing_record.py` — `filed_by` field
- `_verification_report.py` — `verified_by` field
- `_work_unit.py` — `discarded_by` field

## Test run

```
pytest src/aeat/domain/modelos/ -q
# → 147 passed
```

## MERGE-015 closure note

All 5 `_ActorLabel` name collisions are eliminated: 1 in `domain/buckets/` renamed to `BucketActorLabel` (S40), 4 in `domain/modelos/` renamed to `ModeloActorLabel` (S41). All are module-local private Annotated types with identical constraints — the rename is structural disambiguation, not semantic change.
