---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
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

The S115 tests instantiate `AeatAuthenticator`, call the real invalidation helper with a sensitive storage basename, drive `_run_login_probe()` through a browser-context stand-in that raises a sensitive payload, and inject real certificate-health callables that raise sensitive failure strings. Assertions cover rendered errors, structured context, model serialization, translated health summaries, suppressed exception causes, and captured log messages.

Status: closed.

## S115-004 | MEDIUM | Certificate-health describe diagnostics rendered raw exception text

Mandatory review found that `describe()` still rendered raw exception text into `AuthProviderDescription.health_summary` and into the unexpected `AuthValidationError` path. That auth surface is adjacent to persisted-session diagnostics and could expose certificate paths or parser details.

Resolution: `describe()` now returns the localized `application.auth.certificate.health.unavailable` summary for known certificate-health failures, raises `AuthValidationError` with the same translated-message key for unexpected failures, and logs only the exception type at debug level.

Status: closed.

## S115-005 | MEDIUM | Persisted invalidation could retain raw exception context

Mandatory review found that malformed load, malformed metadata, and resume failure invalidations were invoked inside `except` frames after interpolating raw exception text into the invalidation reason. Even with a redacted public message, verbose traceback paths could retain sensitive underlying context.

Resolution: those branches now log exception type at debug level, pass stable reason strings into `_raise_invalid_persisted_state()`, and raise the redacted invalidation outside the raw exception-message rendering path where practical. The invalidation helper also uses explicit context suppression.

Status: closed.

## S115-006 | INFO | Persisted store contract remains a follow-up row

This step redacts authenticator diagnostics around persisted session invalidation and probe failure. The session-store schema, storage-state path contract, and encryption/privacy organization remain tracked by the pending AFR-015 / W12.P26.S117 `_session_store.py` row.

Status: open follow-up.
