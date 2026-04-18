---
tags:
  - '#exec'
  - '#auth-protocol'
date: '2026-04-18'
related:
  - '[[2026-04-18-auth-protocol-plan]]'
---

# `auth-protocol` `phase-1` `step-4`

Completed focused verification and lint cleanup for the auth-protocol refactor.

- Modified: `src/aeat/auth/test_authenticator.py`
- Modified: `src/aeat/submission/test_preflight.py`
- Modified: `src/aeat/submission/test_engine.py`
- Modified: `src/aeat/submission/test_live_submission.py`
- Modified: `src/aeat/submission/test_safety_helpers.py`
- Modified: `src/aeat/workflow/test_engine.py`

## Description

Updated the affected test doubles so they model provider descriptions instead of certificate-only stubs. Added protocol-conformance coverage for the new auth abstraction, kept the certificate-backed compatibility assertions intact, and cleaned the touched modules until targeted `ruff` checks passed without warnings.

## Tests

Executed `uv run ruff check` across the touched auth, browser, submission, workflow, and CLI modules, then reran the focused pytest batch:

- `uv run pytest src/aeat/auth/test_authenticator.py src/aeat/browser/test_session.py src/aeat/submission/test_preflight.py src/aeat/submission/test_engine.py src/aeat/submission/test_safety_helpers.py src/aeat/workflow/test_engine.py src/aeat/cli/_test_doctor.py src/aeat/cli/submission/test_cli.py -q`
