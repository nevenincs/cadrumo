---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-07-17'
body_hash: 'sha256:6b1e953c3fc20f2be8556be2720b1c650687893b1b04aaec7be265523fdfd3a0'
step_id: 'S07'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# refactor auth conftest.py to eliminate wildcard imports

## Scope

- `src/aeat/adapters/outbound/aeat/auth/tests/conftest.py`

## Description

- Refactored `auth/tests/conftest.py` to eliminate the wildcard import of `_authenticator_support`.
- Declared explicit imports for `_isolated_secure_session_backend` and `_settings_factory` fixtures.

## Outcome

Verification via local test execution confirms that fixtures are successfully resolved and outbound auth tests execute without error.

## Notes
