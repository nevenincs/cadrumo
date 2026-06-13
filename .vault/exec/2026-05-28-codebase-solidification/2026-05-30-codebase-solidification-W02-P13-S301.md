---
step_id: S301
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-iota6
commit: ae373e0f4
status: closed
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P13.S301

Added to `src/aeat/core/external_constants.py`:
- `JSON_MIME_TYPE: Final[str] = "application/json"`
- `CSV_MIME_TYPE: Final[str] = "text/csv"`

Both are `Final[str]` module-level constants following the existing `BINARY_MIME_TYPE` pattern.
