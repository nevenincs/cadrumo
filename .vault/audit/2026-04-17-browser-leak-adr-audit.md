---
tags:
  - "#audit"
  - "#browser-leak"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-16-chromium-leak-research]]"
  - "[[2026-04-17-browser-leak-adr]]"
---

# `browser-leak` Code Review

ADR-001 | HIGH | auth-gate contract was too weak
The first ADR draft allowed PR `#181` compatibility to remain optional by saying the session contract "may be closable". Issue `#190` requires a mandatory async `close()` on `aeat.adapters.outbound.aeat.auth._authenticator.BrowserSessionLike` and removal of the duck-typed fallback. The ADR was revised to pin that requirement explicitly.

ADR-002 | MEDIUM | repeated `create_context()` semantics were under-specified
The first ADR draft acknowledged repeated-session safety but did not decide whether a session should reuse, replace, or reject a second live browser/context. That ambiguity could permit implementations that invalidate caller-owned contexts behind the caller's back. The ADR was revised to require one live browser per `BrowserSession` instance and to raise on a second `create_context()` until `close()` is called.

ADR-003 | LOW | scope wording drifted wider than issue `#190`
The first ADR draft described a generic contract extension without naming the narrow auth-side target. The ADR was revised so the main-branch implementation scope stays limited to `aeat.adapters.outbound.aeat.browser.BrowserSession` plus direct callers/tests, while the forward-compat requirement names `aeat.adapters.outbound.aeat.auth._authenticator.BrowserSessionLike` specifically.
