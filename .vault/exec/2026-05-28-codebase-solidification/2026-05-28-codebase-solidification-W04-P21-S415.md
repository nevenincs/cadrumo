---
step_id: "S415"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W04.P21.S415

## Outcome

`raise ValueError(...)` at `_binding_prefill.py:347` replaced with
`ModeloApplicabilityFilterError` (W2-enrolled). Lazy import used to avoid
circular import through `calculations → modelo._actions → live → calculations`.
Plan step closed.
