---
tags:
  - '#exec'
  - '#auth-protocol'
date: '2026-04-18'
related:
  - '[[2026-04-18-auth-protocol-plan]]'
---

# `auth-protocol` `phase-1` summary

Completed the session-shape refactor and provider-protocol decoupling needed for issue `#281`.

- Modified: `src/aeat/auth/_authenticator.py`
- Modified: `src/aeat/browser/session.py`
- Modified: `src/aeat/submission/_engine.py`
- Modified: `src/aeat/workflow/_engine.py`
- Created: `src/aeat/auth/_providers.py`
- Created: `2026-04-18-auth-protocol-review`

## Description

Introduced the shared `AuthProvider` contract, generalized the auth session and login-assertion models, and replaced the certificate-only browser seam with a provisioner contract. Updated submission, workflow, doctor, and CLI submission paths to consume provider descriptions instead of certificate backends while keeping the live-write gate anchored in `AeatAccessGate`.

## Tests

Verified the refactor with focused and broad unit coverage plus linting:

- `uv run pytest src/aeat/auth/test_authenticator.py src/aeat/browser/test_session.py src/aeat/submission/test_preflight.py src/aeat/submission/test_engine.py src/aeat/submission/test_safety_helpers.py src/aeat/workflow/test_engine.py src/aeat/cli/_test_doctor.py src/aeat/cli/submission/test_cli.py -q`
- `uv run pytest src/aeat/auth/test_authenticator.py src/aeat/workflow/test_engine.py src/aeat/cli/_test_doctor.py src/aeat/cli/submission/test_cli.py -q`
- `uv run pytest src/aeat/auth src/aeat/browser src/aeat/submission src/aeat/workflow src/aeat/cli -m unit -q`
- `uv run ruff check src/aeat/auth src/aeat/browser src/aeat/submission src/aeat/workflow src/aeat/cli`

Audit closure is recorded in `2026-04-18-auth-protocol-review`.
