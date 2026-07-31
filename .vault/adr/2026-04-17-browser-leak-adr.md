---
tags:
  - "#adr"
  - "#browser-leak"
date: "2026-04-17"
modified: '2026-07-17'
body_hash: 'sha256:46a39fd390020d6ef5c7410336f750bf9b108081106994ca4e1bb9c8c63e554d'
related:
  - "[[2026-04-16-chromium-leak-research]]"
---
# `browser-leak` adr: `browser-session-browser-ownership` | (**status:** `accepted`)

## Context

`BrowserSession` is the concrete Playwright lifecycle boundary used by AEAT
authentication and Sede read adapters. A browser process cannot be delegated to
a returned context because context closure does not guarantee process teardown,
and partial context construction can fail after Chromium has launched.

## Decision

`src/cadrumo/adapters/outbound/aeat/browser/session.py` owns at most one live
browser at a time. `create_context()` serializes lifecycle mutation, refuses a
second live browser, retains the launched handle before context construction,
and closes that handle on context-construction, evasion, cancellation, or
unexpected failure. Persisted browser state is supplied explicitly as an
in-memory mapping; provider-specific construction arguments arrive through the
single `BrowserContextProvisioner` seam.

`close()` is mandatory, asynchronous, serialized by the same lifecycle lock,
idempotent after successful closure, and clears the retained handle only after
`browser.close()` succeeds. A close failure remains retryable because ownership
is retained. Callers close pages and contexts they create; the component that
constructs `BrowserSession` owns session closure and Playwright shutdown.

The auth provider contract exposes asynchronous `close()`. Certificate and
Cl@ve providers serialize close intent against authentication and verification,
close their active context before the owned browser session, retain resources
whose closure failed, and bound potentially stuck Playwright teardown at the
provider lifecycle boundary. There is no duck-typed optional-close fallback and
no browser-pool or borrowed-ownership compatibility path.

## Consequences

- A session cannot silently replace a caller-owned context or browser.
- Partial launch and context failures have one cleanup path.
- Concurrent authentication, verification, and close operations have explicit
  ownership ordering.
- Failed teardown is visible and retryable instead of being reported as clean.
- Reuse requires successful closure followed by a fresh context creation.

## Verification

Real Playwright lifecycle tests cover successful closure, partial construction
failure, repeated closure, concurrent close intent, retained ownership after
failure, and process reaping. Static protocol checks require the same mandatory
async close surface across concrete providers and browser-session factories.
