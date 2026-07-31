---
step_id: S233
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-07-17'
body_hash: 'sha256:3d1ef4a2a3f7a7e8192500fb701b46688904a455a06887bcf3dbc69e0605337a'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P10.S233

## Outcome

Replaced bare `"draft"` string with `CasillaFieldKind.DRAFT` at `src/aeat/adapters/outbound/aeat/sede/_declarations.py:1471`. Added `CasillaFieldKind` to the existing `from .....domain.calculations.registry import (...)` block.

## Files touched

- `src/aeat/adapters/outbound/aeat/sede/_declarations.py` — 1 import added, 1 comparison replaced
