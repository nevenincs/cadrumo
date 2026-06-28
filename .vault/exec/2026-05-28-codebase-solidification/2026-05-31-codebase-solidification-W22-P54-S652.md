---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S652
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W22.P54.S652`

Rewrote two mock-based test methods in `test_except_clause_narrowing.py` to use constructor injection; removed all `unittest.mock` imports; updated `test_mock_inventory.py` to clear the now-empty documented boundary mock list.

- Modified: `src/aeat/test_except_clause_narrowing.py`
- Modified: `src/aeat/test_mock_inventory.py`

## Description

`AeatAuthenticator.__init__` already exposes a `certificate_health_check` constructor parameter (a `CertificateHealthCheck` Protocol callable) designed for injection. Both tests were rewritten to pass a local callable that raises the target exception type directly, eliminating the `patch.object` pattern entirely.

Design: injection callables are method-local (defined inside each test method), matching the minimal scope convention used elsewhere in the suite. `_DOCUMENTED_BOUNDARY_MOCKS` in `test_mock_inventory.py` was cleared to an empty frozenset since no mock usage remains in the codebase.

## Tests

Grep-post: zero `from unittest.mock import patch` and zero `patch.object(` in `test_except_clause_narrowing.py`. Both rewritten tests (`test_unexpected_exception_raises_auth_validation_error`, `test_certificate_error_returns_unavailable_description`) pass. `test_mock_inventory` ratchet passes (empty documented set, zero undocumented imports found). 3/3 `TestAuthenticatorDescribeNarrowing` tests green.
