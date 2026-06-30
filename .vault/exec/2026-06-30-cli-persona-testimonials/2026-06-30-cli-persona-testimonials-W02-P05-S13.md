---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S13'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Harden workflow bucket-scan ambiguity and tombstone behavior

## Scope

- `src/aeat/application/workflow/_profile_bucket_scan.py`

## Description

- Harden shared bucket-scan resolution so tombstoned UUIDs are excluded from
  live resolution by default.
- Preserve `include_tombstoned=True` for explicit inspect callers.
- Verify resolver behavior with workflow tests.

## Outcome

Commit `e6c0295` updated
`src/aeat/application/workflow/_profile_bucket_scan.py` so
`resolve_profile_bucket` applies the lifecycle filter consistently to UUID and
label paths. `include_tombstoned=True` still resolves tombstoned UUIDs for
inspection.

## Notes

Final workflow resolver verification passed 13 tests.
