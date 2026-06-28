---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S115'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-013 for AEAT authenticator diagnostics

## Scope

- `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`
- `src/aeat/adapters/outbound/aeat/auth/test_authenticator.py`

## Description

- Classify the authenticator persisted-session boundary as a `manifest-discovery` surface with `manifest-bucket` and `plain-file` signals.
- Replace persisted-session invalidation errors that rendered raw reasons with a stable redacted message, a translated-message key, and structured context containing only `<persisted-aeat-session>` and a non-sensitive reason code.
- Replace persisted-session fallback logging of the storage-state path and exception text with the same redacted session label and reason code.
- Replace login-probe navigation failure diagnostics that logged raw targets and exception strings with a debug diagnostic carrying only `<aeat-login-probe>` and the exception type.
- Replace certificate-health describe failures that rendered raw exception strings with a localized redacted summary and exception-type-only debug diagnostics.
- Move malformed persisted-session load, metadata parse, and resume invalidation raises out of raw exception-message rendering paths, preserving debug-level failure type diagnostics while preventing raw exception strings from reaching the raised invalidation error.
- Add real authenticator tests that drive the invalidation helper, login-probe failure path, and certificate-health describe failure paths directly, asserting that rendered errors, structured output, and captured logs do not expose sensitive basenames, absolute paths, or exception payload text.

## Outcome

- `uv run ruff check src/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/auth/test_authenticator.py` passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/auth/test_authenticator.py` passed: 45 passed.
- `uv run pytest -q src/aeat/adapters/outbound/aeat/auth/test_authenticator_translated_message.py` passed: 8 passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S115` closed the step row.

## Notes

- S115 targets failure and invalidation diagnostics. It does not change the persisted session schema or storage-state encryption behavior; the follow-up AFR-015 / `_session_store.py` row remains the owning surface for the store contract.
