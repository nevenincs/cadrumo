---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S583
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W11.P42.S583`

Enrolled 8 bare `"utf-8"` sites in `src/aeat/adapters/outbound/google/_session_store.py` with `UTF_8_ENCODING`.

- Modified: `src/aeat/adapters/outbound/google/_session_store.py`

## Grep post-condition

Before: 8 bare `"utf-8"` literals — 4x `.encode("utf-8")` (lines 44, 71, 98, 125) + 4x `.decode("utf-8")` (lines 59, 86, 113, 140)
After: 0 bare `"utf-8"` literals

All JSON payload encode/decode sites replaced with `UTF_8_ENCODING`.
Import added via `....core.external_constants`.
