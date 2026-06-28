---
step_id: "S420"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W04.P21.S420

## Outcome

Silent `except Exception: profile_tax_id = ""` at `auth/_operator.py:647`
(profile tax-id probe) narrowed to `except (OSError, AeatError, AttributeError,
LookupError)` with `_log.debug(..., exc_info=True)`. Confirmed at HEAD.
Plan step closed.
