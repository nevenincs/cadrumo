---
tags:
  - '#exec'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-17'
body_hash: 'sha256:35d91bd06408b7be1f992269838956e2e9c50d45478bd9b8685193475f4bb7fd'
step_id: 'S05'
related:
  - "[[2026-07-16-protected-browser-certificate-auth-plan]]"
---
# Make certificate context teardown bounded retryable and primary-exception preserving

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`
- `src/cadrumo/adapters/outbound/aeat/auth/_browser_lifecycle.py`

## Description

- Bound certificate context and browser-session close calls with the configured browser close timeout.
- Retain failed resource handles for a later close attempt instead of clearing ownership early.
- Route owner-level cleanup through the central asynchronous cleanup authority so cancellation and primary errors remain primary while cleanup failures stay retryable.

## Outcome

Certificate teardown is finite, failed owners remain reachable, and cleanup failure cannot silently replace an active authentication or cancellation exception.

## Notes

Fresh semantic grounding resolved `close_owned_browser_context()`, `close_owned_browser_session()`, `close_async_resources()`, and `AsyncResourceCleanupError.retry_cleanup()`. Real-resource timeout, retry, and process-reaping cases passed in the 44-test focused matrix.
