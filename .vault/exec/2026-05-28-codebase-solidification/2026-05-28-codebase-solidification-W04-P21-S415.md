---
step_id: "S415"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-07-17'
body_hash: 'sha256:f3d92b31d8d8d7c5c80b7d4e2052715bc942635f0dc0daad201ccc997b0f52f1'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W04.P21.S415

## Outcome

`raise ValueError(...)` at `_binding_prefill.py:347` replaced with
`ModeloApplicabilityFilterError` (W2-enrolled). Lazy import used to avoid
circular import through `calculations → modelo._actions → live → calculations`.
Plan step closed.
