---
tags:
  - "#audit"
  - "#browser-leak"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-16-chromium-leak-research]]"
  - "[[2026-04-17-browser-leak-adr]]"
  - "[[2026-04-17-browser-leak-plan]]"
---

# `browser-leak` Code Review

PLAN-001 | MEDIUM | justificante cleanup lacked deterministic coverage
The first plan draft included `_verify.py` in scope but only referenced the existing live smoke path. That was insufficient to prove the own-session `close()` path and the borrowed-session non-close contract. The plan was revised to require deterministic unit coverage if `_verify.py` remains in scope.

PLAN-002 | LOW | public example drift needed an explicit scope call
The first plan draft did not say what to do with the stale `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/__init__.py` example that still shows `context.close()` as the full cleanup story. The plan now treats that example as an explicit out-of-scope documentation follow-up unless correctness work forces a code touch there.
