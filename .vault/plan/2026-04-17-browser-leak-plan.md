---
tags:
  - "#plan"
  - "#browser-leak"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-16-chromium-leak-research]]"
  - "[[2026-04-17-browser-leak-adr]]"
  - "[[2026-04-17-browser-leak-adr-audit]]"
---

# `browser-leak` `phase1` plan

Implement browser-session lifecycle hardening for issue `#190` by retaining the launched browser inside `BrowserSession`, adding an idempotent async `close()`, cleaning up partial launch and context failures, and preventing a second `create_context()` while a live browser remains active.

## Proposed Changes

- Update `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py` to own browser lifetime explicitly and enforce single-live-browser semantics.
- Make `BrowserSession.close()` safe to call multiple times and ensure it tears down any partially initialized resources.
- Propagate explicit session cleanup to direct owners in `src/aeat/entrypoints/cli/browser/health.py` and `src/aeat/domain/justificante/_verify.py`.
- Align tests with the new lifecycle contract and the forward-compat expectation from PR `#181`.
- Keep scope limited to `aeat.adapters.outbound.aeat.browser` and the direct owner cleanup call sites/tests.

## Tasks

- `Refactor BrowserSession to retain the launched browser and track lifecycle state`
- `Add idempotent close() handling for normal shutdown and partial launch/context failure paths`
- `Reject repeated create_context() calls while a browser is still live`
- `Update browser-health owner cleanup to close the session before playwright.stop()`
- `Update justificante local-session cleanup to close the BrowserSession on the own-browser path`
- `Add deterministic unit coverage for verify_csv() own-session close and borrowed-session non-close behavior if justificante cleanup remains in scope`
- `Add session lifecycle regression coverage in src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py`
- `Add owner-cleanup assertions in src/aeat/entrypoints/cli/browser/test_health.py`
- `Close the session in src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_live_evasion.py`
- `Verify forward compatibility with PR #181's required async BrowserSessionLike.close() contract without editing absent branch files`

## Parallelization

The `BrowserSession` contract change should land first because every cleanup caller and test depends on it. After that, direct owner cleanup call sites and their tests can be updated in parallel. Live-path adjustments should remain isolated from the unit-test work unless the contract change forces them.

## Verification

- Run targeted unit tests for `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py` and `src/aeat/entrypoints/cli/browser/test_health.py`.
- Run the affected browser and justificante tests that exercise the updated owner-cleanup paths, including new deterministic unit coverage if `_verify.py` changes.
- Run lint and typecheck on touched Python surfaces.
- Keep live verification limited to already gated paths only.
- Re-check the open PR `#181` contract and confirm the landed `BrowserSession.close()` semantics satisfy the auth-gate cleanup path without broadening scope into absent branch files.
- Treat the stale `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/__init__.py` example as an explicit out-of-scope documentation follow-up unless the implementation touches that file for correctness.
