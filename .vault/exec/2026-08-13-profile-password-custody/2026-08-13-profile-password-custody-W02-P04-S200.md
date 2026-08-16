---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:17e2412e40b7314e617596dc261b91f616a920f2246ccbce50799b7699fed049'
step_id: 'S200'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make closing a bucket session retire the process-local record authority with it, since a latched authority for the same profile survives the close, so logged out and record authority gone are different states within one process and a health check after a logout can still read facts through the surviving authority, which is why a shipped cold-profile test passes while exercising a profile that is not genuinely locked

## Scope

- `src/cadrumo/application/user_profile/_profile_record_repository.py and src/cadrumo/adapters/persistence/storage/custody/`

## Description

- Add the closed predicate to the session port so the application can ask it.
- Make record-authority resolution require a session that can still decrypt,
  not merely one that names the right bucket.
- Prove it with a test that fails if a retired authority survives its session.

## Outcome

The defect was real and the reason it was reachable is worth stating, because
it is not the obvious one.

A bucket session is sealed IN PLACE: closing it zeroises its key buffers rather
than replacing the object. So a closed session keeps naming its bucket and
keeps satisfying an identity comparison long after its key is gone. Any
authority that resolved on identity alone therefore saw a present, matching,
and entirely unusable session -- which is how "logged out" and "record
authority gone" became two different states inside one process, and how a
health check after a logout could still read facts through the survivor.

The application layer could not previously detect this, and that was the
blocking half: the closed predicate existed on the concrete session but was
absent from the port the application holds, so the question could not even be
asked across the boundary. Adding it to the port is what made the fix
expressible.

Resolution now asks both questions together -- does this session serve the
profile, and is it still unsealed -- which turns "a session exists for this
profile" into "a session that can still decrypt exists for this profile", the
property a record authority actually depends on. Both are in-memory reads, so
the check is cheap enough to ask on every resolution rather than cached into a
staleness problem of its own.

A dedicated regression covers it and passes: three cases asserting the derived
authority retires with the custody session that backs it.

## Notes

The row noted a shipped cold-profile test that passed while exercising a
profile which was not genuinely locked. That is the same root cause seen from
the test side: a sealed-in-place session satisfied the fixture's notion of
"closed" while still resolving, so the test proved less than its name claimed.
