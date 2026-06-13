---
step_id: S235
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P10.S235

## Outcome

Converted all `match field.kind` arms in `src/aeat/application/filing/_export.py` from bare strings to `CasillaFieldKind.<MEMBER>` patterns. Also replaced two additional bare `"binding"` comparisons at lines 360/371 and one bare `"casilla"` comparison at line 626 found by the enrollment test sweep. Added `CasillaFieldKind` to the existing registry import block.

## Files touched

- `src/aeat/application/filing/_export.py` — 1 import added, 10 bare strings replaced (7 match arms + 3 set-comprehension guards)
