---
step_id: "S419"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W04.P21.S419

## Outcome

Silent `except Exception: return None` at `auth/_operator.py:900` (certificate load)
narrowed to `except (OSError, ValueError, AeatError)` with `_log.warning(...,
exc_info=True)`. `get_logger` + `_log` added to the module. Confirmed at HEAD.
Plan step closed.
