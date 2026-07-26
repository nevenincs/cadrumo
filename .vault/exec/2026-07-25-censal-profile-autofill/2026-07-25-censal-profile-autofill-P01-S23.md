---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S23'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Salvage the authenticated Clave session a post-auth navigation failure was closing unread, so a spent second factor becomes a retryable navigation

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil.py`

## Description

- Establish what a post-authentication failure actually tears down before proposing anything, finding the browser context and the browser session both closed and no stored session ever written.
- Confirm the reuse path already probes for a live session before authenticating, and that the store is shared across processes, so neither needed changing.
- Verify that a rejected probe falls through to a fresh login, which is what makes it safe to keep a session whose usability is uncertain.
- Establish whether the timeout branch can tell an approved login from an unapproved one, finding the cancel already guards on the wait-page marker and so never cancels an approval.
- Capture and persist the context's state before the teardown that was discarding it.
- Skip the write when the capture carries no cookies, which is a fact about the capture rather than an inference about the operator.
- Swallow and log every salvage failure, so recovering a session cannot mask the login error that caused it.
- Leave the cancel logic untouched, since it is already correct in the case that matters.
- Pin the persistence half against the real encrypted store, and name the half that cannot be proven offline rather than simulating it.

## Outcome

Five tests in `src/cadrumo/adapters/outbound/aeat/auth/tests/test_clave_session_persistence_boundary.py`, covering the persistence half against the real store with no browser.

`uv run --no-sync pytest` over the auth adapter unit suite reported `167 passed, 7 deselected in 156.03s`.

`uv run --no-sync ruff check`, `ruff format` and `ty check` all reported clean on the driver and the new tests.

One change covered both post-auth failures rather than two, confirmed by walking the syntax tree: the challenge, the landing wait and the state capture all sit inside the same handler, so the timeout raises through it as well.

## Notes

The reported defect was that a valid session is discarded. The code's defect is that no session is ever saved, which is a different thing and changes the fix. The state is captured only after the challenge returns, and the post-authentication navigation runs inside that call, so a failure there closes a context whose cookies were never read. AEAT holds a session open and the application holds nothing. The distinction matters because a repair aimed at reusing a held session would have found none to reuse.

Keeping a session whose usability is unknown is safe for one reason, and it is worth stating with its qualification rather than as a clean claim. The reuse path probes before trusting, so a salvaged session that turns out dead is rejected and the caller falls through to a fresh login, which is exactly the present behaviour. It is therefore not worse for the OPERATOR. It is not free: the probe reaches a browser launch after its cheap checks, so an unusable salvaged session costs one wasted round trip. Against a second authentication that requires the operator physically present inside a window that cannot be extended, that is not a close trade.

The timeout branch resolved better than the precondition anticipated. The question was whether an approved-but-undetected login could be told from one never approved, with instructions to report rather than guess if it could not. It can: the cancel returns early unless the page is still on the wait page, and an approved request has navigated away, so an approval is never cancelled. No guess was needed and the cancel was left alone. The residual is that the marker separates waiting from not-waiting, which is weaker than approved, since a navigated-away page could be an error page. That is sufficient for the cancel decision and irrelevant to the capture, because the probe adjudicates afterwards.

A question raised during review resolved on evidence that had been reported incompletely. A failed probe never deletes the persisted session, which sounded like it would leave a dead salvaged session re-probed forever. It does not: the authenticate path invalidates a session its resume step refuses, so the next real authentication cleans it up. The probe's refusal to delete is deliberate, because it exists as a side-effect-free diagnostic.

The behaviour itself is unverified and this record should not be read as claiming otherwise. The adapter's offline suite does not drive the page flow, and a page double would assert that the double behaves at exactly the boundary the driver exists to negotiate. What is shown is that the change is well formed and breaks nothing. Confirming that an operator is not prompted twice needs a live approval and a deliberately induced post-auth failure. The salvage logs at info when it fires, which is the cheap signal to look for in that run before checking whether the second prompt appears.
