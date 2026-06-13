---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W04.F21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-code-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-persona-testimonials-audit]]'
---

# `live-iva-compensation-wallet` `W04.F21`

Kept auth readiness inspection inside the config/auth domain when workspace secure-object rows are unreadable.

- Modified: `src/aeat/application/state_projection.py`
- Modified: `src/aeat/application/auth/_operator.py`
- Modified: `src/aeat/application/auth/test_operator.py`

## Description

The 2026-05-22 config-domain persona pass found that `aeat config auth status` failed on an unreadable filing-draft row. That row belongs to workspace/calculation state and must remain visible through `config repair`, but it should not block a local auth-readiness question.

The canonical operator projection now has opt-out switches for workspace counters and pending-obligation calculation. `auth status` and `auth test` keep using the canonical projection for active-profile/auth readiness, but they disable those broader views. Overview-style surfaces keep the default full projection.

The regression uses real encrypted storage: it registers an active profile, configures certificate auth, writes a filing draft under a rotated ephemeral master key, then verifies auth status still returns provider/profile readiness instead of raising a secure-object unreadable error.

No live AEAT operation was performed in this step.

## Tests

- `uv run pytest src/aeat/application/auth/test_operator.py src/aeat/application/test_state_projection.py -q --disable-warnings` completed with 34 passed.
- `uv run pytest src/aeat/application/auth/test_operator.py src/aeat/application/test_state_projection.py src/aeat/application/test_diagnostics.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_error_registry_contract.py -q --disable-warnings` completed with 85 passed.
- `uv run ruff check src/aeat/application/state_projection.py src/aeat/application/auth/_operator.py src/aeat/application/auth/test_operator.py src/aeat/core/errors/registry/_application.py src/aeat/application/diagnostics.py src/aeat/application/test_diagnostics.py` passed.
- `uv run aeat config auth status` completed successfully and reported local auth/profile readiness.
