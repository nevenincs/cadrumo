---
step_id: "S412"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-07-17'
body_hash: 'sha256:5c795fd38958c147f802dff998f4bfaed7ecf20f7ff19ac4d25f249589108fa4'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W04.P21.S412

## Outcome

`ProfileRegistrationError(CoreError)` introduced in `src/aeat/core/profile.py`.
Bare `raise RuntimeError(...)` at line 82 replaced. Registry entry added to
`_core.py` under `INTERNAL_PROFILE_REGISTRATION`. Confirmed at HEAD by peer
campaign commit `e30370bdc`. Plan step closed via `vault plan step check`.

## Verification

`src/aeat/application/test_w04_p21_survivors.py` — 17 tests pass.
