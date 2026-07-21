---
tags:
  - '#exec'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-16-protected-browser-certificate-auth-plan]]"
---
# Delete implicit plaintext profile storage-state consumption from fresh provider sessions and make every persistence source explicit

## Scope

- `src/cadrumo/adapters/outbound/aeat/browser/session.py`
- `src/cadrumo/adapters/outbound/aeat/auth/`

## Description

- Remove the browser profile filesystem storage-state field and its implicit preload path.
- Restrict `BrowserSessionLike.create_context()` and `BrowserSession.create_context()` to an optional validated in-memory storage-state mapping.
- Route provider resume and downstream browser construction through encrypted session objects whose historical path field is only a logical object key.

## Outcome

Fresh provider contexts cannot consume a plaintext profile cookie file. Browser state enters Playwright only when a caller explicitly supplies the in-memory mapping loaded and validated through the encrypted session repository.

## Notes

Fresh semantic grounding followed code-index job `a4075877bc0540e2b605bf5a47c2ce89`. Exact source inspection found no filesystem storage-state argument on either browser context contract. The focused auth/browser real-behavior matrix passed 44 tests in 101.19 seconds.
