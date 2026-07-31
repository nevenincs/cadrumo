---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-07-17'
body_hash: 'sha256:c472f59c021aa9397edaf1270154c8c5210d8608f613113db517a45859a327c5'
step_id: S582
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W11.P42.S582`

Enrolled 9 bare `"utf-8"` sites in `src/aeat/locales/manager.py` with `UTF_8_ENCODING`.

- Modified: `src/aeat/locales/manager.py`

## Grep post-condition

Before: 9 bare `"utf-8"` literals (lines 68, 105, 158, 291, 311, 328, 353, 365, 385)
After: 0 bare `"utf-8"` literals

All 9 sites replaced with `UTF_8_ENCODING` from `aeat.core.external_constants`.
Import added at module top.
