---
step_id: S265
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-30-codebase-solidification-audit]]"
---

# codebase-solidification W02.P11.S265

**Raise site:** `src/aeat/application/diagnostics.py:416`

**Change:** Replaced `raise TypeError("SiteHealthError carried a non-SiteHealthStatus payload")` with `raise DiagnosticModelError(...)`. `DiagnosticModelError` was already imported from `._errors` at module top.

**Tests:** `test_survivor_envelope_enrollment.py` — 8 tests pass (includes `DiagnosticModelError` enrollment assertion).

**Commit:** `d76cbf66e`
