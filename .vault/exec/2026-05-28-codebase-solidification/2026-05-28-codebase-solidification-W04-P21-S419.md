---
step_id: "S419"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-07-17'
body_hash: 'sha256:38c6aad3101594a7cdbbe5c026f6552618fba65f0c87ffbb53f9744c79f385b5'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W04.P21.S419

## Outcome

Silent `except Exception: return None` at `auth/_operator.py:900` (certificate load)
narrowed to `except (OSError, ValueError, AeatError)` with `_log.warning(...,
exc_info=True)`. `get_logger` + `_log` added to the module. Confirmed at HEAD.
Plan step closed.
