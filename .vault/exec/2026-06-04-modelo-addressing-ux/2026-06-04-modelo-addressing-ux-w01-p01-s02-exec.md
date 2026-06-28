---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S02'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P01.S02 active and explicit bucket resolution

Scope:
- `src/aeat/application/modelo/_selectors.py`

## Description

- Add `resolve_modelo_work_bucket`.
- Resolve explicit selector `bucket_id` before consulting the active profile bucket.
- Refuse with a typed no-active-bucket error when no explicit bucket or active profile bucket exists.

## Outcome

Modelo work selectors can now resolve the bucket axis consistently for both normal active-profile use and advanced explicit-bucket addressing.

## Notes

- Real repository-backed tests cover active-bucket and explicit-bucket behavior.
