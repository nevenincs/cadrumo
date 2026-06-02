---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S115]]'
---

# `secure-storage-production-hardening` Code Review

## S115-001 | LOW | Persisted-session invalidation rendered raw storage diagnostics

Initial audit found that persisted AEAT browser-session invalidation raised the raw invalidation reason and logged the storage-state path. For auth session state, those strings can carry profile paths, filenames, certificate-adjacent identifiers, or parser diagnostics that do not need to reach operator-facing output.

Resolution: `_raise_invalid_persisted_state()` now maps raw invalidation reasons to non-sensitive reason codes, invalidates the store, and raises `_PersistedSessionInvalidError` with a stable redacted message, translated-message key, and structured context containing only `<persisted-aeat-session>` and the reason code. Fallback logging now uses the same redacted context instead of the storage path or raw exception text.

Status: closed.

## S115-002 | LOW | Login-probe navigation failures logged raw target and exception text

Initial audit found that `_run_login_probe()` rendered the raw exception string into `AeatLoginAssertion.error_message` and logged the raw target URL with traceback details. Browser navigation exceptions can include provider payload snippets, request targets, local browser diagnostics, or profile-specific data.

Resolution: `_run_login_probe()` now records only the exception type in the assertion and logs a debug diagnostic with `<aeat-login-probe>` plus the failure type. The probe still returns an invalid assertion rather than swallowing the failure silently.

Status: closed.

## S115-003 | INFO | Tests exercise the real auth boundaries

The S115 tests instantiate `AeatAuthenticator`, call the real invalidation helper with a sensitive storage basename, and drive `_run_login_probe()` through a browser-context stand-in that raises a sensitive payload. Assertions cover rendered errors, structured context, model serialization, and captured log messages.

Status: closed.

## S115-004 | INFO | Persisted store contract remains a follow-up row

This step redacts authenticator diagnostics around persisted session invalidation and probe failure. The session-store schema, storage-state path contract, and encryption/privacy organization remain tracked by the pending AFR-015 / W12.P26.S117 `_session_store.py` row.

Status: open follow-up.
