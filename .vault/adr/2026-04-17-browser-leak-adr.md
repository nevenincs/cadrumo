---
tags:
  - "#adr"
  - "#browser-leak"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-16-chromium-leak-research]]"
---

# `browser-leak` adr: `browser-session-browser-ownership` | (**status:** `accepted`)

## Problem Statement

`BrowserSession` currently launches Chromium inside `create_context()` but does not retain the browser handle, expose `close()`, or provide async context-manager support. That makes the browser process the wrong ownership boundary: callers can close the returned `BrowserContext`, but the session itself cannot reliably reap the launched Chromium process. Partial-launch failures can also orphan a browser process because there is no session-level cleanup path.

## Considerations

The existing codebase already uses explicit ownership boundaries for cleanup. `src/aeat/entrypoints/cli/browser/health.py::_RealProbe.probe()`, `src/aeat/domain/justificante/_verify.py::verify_csv`, and `src/aeat/status/_reader.py::StatusReader.close()` all close the context they created, and stop Playwright only when they own that lifecycle. The session abstraction should fit that model without shifting cleanup responsibility onto context-owning consumers.

Forward compatibility matters because PR `#181` already assumes session teardown exists. The authenticator cleanup path is prepared to call `close()` on a browser session, but the current `BrowserSessionLike` contract does not guarantee that capability. The fix should make that expectation real without redesigning `BrowserSession` into a pool or making callers like `StatusReader` auto-close sessions they do not own.

## Constraints

The current main branch does not contain `aeat.adapters.outbound.aeat.auth._authenticator`, but issue `#190` is explicitly forward-coupled to PR `#181`. That means the decision must pin the future auth-side contract tightly enough that the browser-layer fix and the auth-gate cleanup path converge on the same mandatory async `close()` surface. `create_context()` must remain safe under partial failures. `close()` must be idempotent and safe under repeated calls. The change must preserve the existing context-owned cleanup contract and must not introduce pool semantics.

## Implementation

`BrowserSession` will retain the launched browser process as an owned resource and expose an explicit `close()` coroutine that shuts it down. `create_context()` will wrap launch and context creation in failure-safe cleanup so any exception after browser launch closes the browser before the error propagates. A `BrowserSession` instance will own exactly one launched browser at a time; a second `create_context()` call on the same live session is an error and must raise rather than silently replacing or invalidating caller-owned contexts. Reuse requires an explicit `await session.close()` followed by a fresh `create_context()` call.

The main-branch implementation scope is limited to `aeat.adapters.outbound.aeat.browser.BrowserSession` and its direct tests and callers. Separately, when PR `#181` is merged or rebased, `aeat.adapters.outbound.aeat.auth._authenticator.BrowserSessionLike` must declare an async `close()` coroutine explicitly and the duck-typed `getattr(..., "close", None)` fallback must be removed. Context-owning consumers such as `StatusReader` will continue to close only the contexts and pages they create; browser-session teardown remains with the owner that constructed the session.

## Rationale

This makes the browser session the real ownership boundary for the Chromium process, which matches how the auth-gate branch already reasons about leaks. Rejecting repeated `create_context()` calls on a still-live session keeps the fix narrow and safe: no caller-owned context is invalidated behind the caller's back, and there is no accidental slide into browser-pool behavior. It also preserves forward compatibility with PR `#181` by requiring explicit browser-session teardown rather than implied duck typing.

## Consequences

Browser process cleanup becomes deterministic, including on partial-launch failures and repeated shutdown calls. Existing context-owning consumers can keep closing their contexts as they do today, but they must not expect one `BrowserSession` instance to mint multiple concurrent contexts without an intervening `close()`. The main tradeoff is added lifecycle complexity inside `BrowserSession`, plus a deliberate single-live-browser restriction per session instance, but that complexity is necessary to prevent Chromium leaks and to support the authenticator cleanup path without broad API redesign.
