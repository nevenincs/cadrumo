---
tags:
  - '#exec'
  - '#auth-protocol'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-auth-protocol-plan]]'
---

# `auth-protocol` `phase-1` `step-4`

Completed focused verification and lint cleanup for the auth-protocol refactor.

- Modified: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/test_preflight.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/test_engine.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/test_live_submission.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/test_safety_helpers.py`
- Modified: `src/aeat/application/workflow/test_engine.py`

## Description

Updated the affected test doubles so they model provider descriptions instead of certificate-only stubs. Added protocol-conformance coverage for the new auth abstraction, kept the certificate-backed compatibility assertions intact, and cleaned the touched modules until targeted `ruff` checks passed without warnings.

## Tests

Executed `uv run ruff check` across the touched auth, browser, submission, workflow, and CLI modules, then reran the focused pytest batch:

- `uv run pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py src/aeat/adapters/outbound/aeat/export/test_preflight.py src/aeat/adapters/outbound/aeat/export/test_engine.py src/aeat/adapters/outbound/aeat/export/test_safety_helpers.py src/aeat/application/workflow/test_engine.py src/aeat/entrypoints/cli/_test_doctor.py src/aeat/entrypoints/cli/submission/test_cli.py -q`
