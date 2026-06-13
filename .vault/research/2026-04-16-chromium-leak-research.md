---
tags:
  - "#research"
  - "#browser-leak"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-12-playwright-anti-bot-research]]"
---

# `browser-leak` research

## Scope

Investigate why `aeat.adapters.outbound.aeat.browser.BrowserSession` leaks Chromium OS processes, identify the exact ownership gap in the current tree, and record the forward-compatibility requirements imposed by the open AEAT access-gate work in PR `#181`.

## Findings

- The current `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py` launches a fresh Chromium `Browser` inside `create_context()` and immediately discards the handle after calling `browser.new_context(...)`.
- `BrowserSession` has no `close()` coroutine, no `__aenter__` / `__aexit__`, and no retained `self._browser` field, so the launched browser process has no explicit teardown path once the caller closes the returned `BrowserContext`.
- Closing a Playwright `BrowserContext` does not give project code a way to later close the owning `Browser`; once the local `browser` variable is gone, the Chromium child process lifetime is effectively delegated to Playwright/Python internals instead of an explicit project-owned contract.
- The current tree already contains one explicit cleanup contract that treats this as a distinct responsibility: `src/aeat/entrypoints/cli/browser/health.py::_RealProbe.probe()` always runs `context.close()` and `playwright.stop()` in `finally`. `BrowserSession` lacks the analogous browser-level cleanup responsibility.
- The issue is forward-relevant to the open auth-gate PR `#181` (`feature/167-aeat-access-gate`), whose `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` already contains `_close_browser_session()` and comments explicitly stating that the Chromium process leaks unless the browser session exposes a real `close()` path.
- PR `#181`'s `BrowserSessionLike` protocol still only declares `create_context(...)`; the issue scope correctly identifies that this protocol must grow a first-class async `close()` contract once `BrowserSession` owns browser teardown.
- Repeated `create_context()` calls on the same `BrowserSession` instance are currently unbounded: each call launches a new Chromium instance, returns a context, and forgets the corresponding browser. Even if the immediate caller closes the context correctly, the session object itself never proves that the browser process was reaped.
- Failure handling is asymmetric today:
  - If `chromium.launch()` raises, no child process exists yet.
  - If `browser.new_context()` raises after a successful launch, the newly spawned browser is also lost because there is no `finally` path that closes it.
  - If later code closes the context successfully, the project still has no explicit guarantee that the browser process was terminated.

## Recommendation

- Add explicit browser ownership to `BrowserSession`: retain the launched `Browser` on the instance and make teardown a public, idempotent async contract (`close()`).
- Make `create_context()` defensive around partial failures: if launch succeeds but context creation or evasion setup fails, close the just-launched browser before raising.
- Treat repeated session use as a cleanup boundary: before replacing an existing retained browser, close the previous one so `create_context()` cannot accumulate orphaned Chromium processes on a reused session object.
- Keep context ownership with the caller, but keep browser ownership with `BrowserSession`. The session should not assume it can close arbitrary active contexts behind the caller's back; it should guarantee that an explicit `await session.close()` always attempts browser teardown regardless of earlier exceptions.
- Align the fix with PR `#181` by giving the future authenticator path a real async `session.close()` target instead of `getattr(..., "close", None)` duck typing.
- Add unit coverage that proves browser teardown, not just context teardown:
  - one test for explicit `await session.close()` after a successful `create_context()`;
  - one test for launch-success / `new_context()`-failure cleanup;
  - one test for repeated create/close cycles proving the browser close count matches launches and does not grow unbounded.

## Constraints

- The current main branch does not contain `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py`; that code is only present on open PR `#181`. The fix therefore has to land in `aeat.adapters.outbound.aeat.browser` with forward-compatible semantics rather than by patching the auth module directly in this worktree.
- Tests must follow the repo mandate: real-behaviour class doubles only, no `unittest.mock`, monkeypatch-driven behavioural substitution, `skip`, or tautological assertions.
- The issue is specifically about browser-process cleanup, not about redesigning `BrowserSession` into a browser pool or changing the single-browser-per-session assumption.
