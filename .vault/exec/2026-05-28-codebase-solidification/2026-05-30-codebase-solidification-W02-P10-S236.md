---
step_id: S236
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P10.S236

## Outcome

Replaced all bare `"binding"` / `"casilla"` strings in `src/aeat/domain/calculations/registry/_export.py` with `CasillaFieldKind.BINDING` / `CasillaFieldKind.CASILLA`. Added `CasillaFieldKind` to the consolidated `from ._schema import (...)` block (merged the duplicate import line).

## Files touched

- `src/aeat/domain/calculations/registry/_export.py` — 1 import added (consolidated), 4 bare strings replaced (lines 151, 156, 167, 186)
