---
step_id: "S416"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-07-17'
body_hash: 'sha256:1518c859b4caa63675990c2a709f1f91002598721c1912cdaab5f3fa51b7d045'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W04.P21.S416

## Outcome

`AuthDiagnosticPayloadError(CoreValidationError)` introduced in
`src/aeat/application/auth/_errors.py`. Two bare `raise ValueError(...)` at
`_diagnostics.py:219, 226` replaced. Registry entry added under
`REFUSED_AUTH_DIAGNOSTIC_PAYLOAD`. Plan step closed.
