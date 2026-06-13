---
step_id: S227
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P10.S227

## Outcome

Deleted local `_now_utc` helper at `src/aeat/application/inventory/_service.py:97` (was `return datetime.now(tz=UTC)`). Added `from ...core.time import _now as _now_utc` canonical alias. Removed orphaned `UTC` from the `datetime` stdlib import. All four call-sites (`lines 213, 281, 312, 350`) now resolve through the canonical clock without any call-site change.

## Files touched

- `src/aeat/application/inventory/_service.py` — delete local helper, add canonical import, remove UTC from stdlib import
