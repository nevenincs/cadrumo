---
step_id: "S416"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W04.P21.S416

## Outcome

`AuthDiagnosticPayloadError(CoreValidationError)` introduced in
`src/aeat/application/auth/_errors.py`. Two bare `raise ValueError(...)` at
`_diagnostics.py:219, 226` replaced. Registry entry added under
`REFUSED_AUTH_DIAGNOSTIC_PAYLOAD`. Plan step closed.
