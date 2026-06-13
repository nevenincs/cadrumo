---
step_id: S66
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S66 — auth banner log routing tests

## Outcome

Extended `src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` with three
real-behavior tests exercising `_render_progress_banner` after the S65 change:

- `test_render_progress_banner_emits_via_logger_not_stdout` — asserts
  `capsys.readouterr()` returns empty strings for both out and err, and that a
  log record with `auth.waiting_banner` in its message is present.
- `test_render_progress_banner_qr_branch_logged` — covers the QR branch
  (used_non_qr_fallback=False, verification_code=None).
- `test_render_progress_banner_non_qr_branch_logged` — covers the non-QR
  branch (used_non_qr_fallback=True, verification_code="XYZ").

## Files touched

- `src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`

## Verification

77 tests pass. Commit: 2f51c3e0d. `vault plan step check S66` applied.
