---
step_id: S229
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P10.S229

## Outcome

Deleted local `_utc_now` helper at `src/aeat/application/storage/calc_sheets/_records.py:471` (was `return datetime.now(tz=UTC)`). Added `from ....core.time import _now as _utc_now` canonical re-export at module level. The `_engine.py` consumer continues to import `_utc_now` from `_records` without any call-site change — the alias preserves the existing public symbol. `UTC` remains in the stdlib import because it is still used by the `_exported_at_is_utc` model validator.

## Files touched

- `src/aeat/application/storage/calc_sheets/_records.py` — delete local helper, add canonical import alias
