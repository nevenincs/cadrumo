---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:a52d85c8e3fcdc73441a6fd27aab5eabb6510d08f59eb4cfb8d97b28326db0cf'
step_id: 'S85'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh delete the two session-lifetime manifest reads now that nothing writes the file they consult, since with no writer remaining they are permanently-fallback dead paths that already degrade to the settings defaults, and the removal ripples through the forwarding port into the login session so it wants its own commit rather than riding a key-derivation change

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py and src/cadrumo/application/user_profile/_login_session.py`

## Description

- Confirm no writer remains for the session-lifetime manifest file.
- Verify both dead reads are gone: the storage-side module and the login
  session.

## Outcome

Both halves are absent from the tree and were verified against HEAD rather
than assumed from the Step's premise.

The storage-side module that carried one of the reads no longer exists at all.
The login session retains four occurrences of the word "manifest", and every
one of them is docstring prose describing the route as REMOVED — "current
capsules deliberately have no plaintext manifest", and a note that session
resolution does not go through the removed manifest/provider route. None is a
live read.

That distinction is the whole verification: a grep for the term finds four
hits and would have read as incomplete work, while the surviving text is the
record of the removal rather than the thing to be removed. Prose that explains
why a path is gone is worth keeping; the Step asked for the reads, and there
are none.

## Notes

This row was found already landed by other work rather than executed here. It
is recorded as complete on verification against HEAD, not on the assumption
that an unchecked box meant undone work — the two are different states and the
campaign has been bitten by conflating them.
