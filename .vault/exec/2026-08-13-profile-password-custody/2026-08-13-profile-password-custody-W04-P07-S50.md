---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:9147841d38e2185af7db96454ff5bcfae647fab363f2c16fea26fd9dd2688a0e'
step_id: 'S50'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make the profile-record session authority re-derive when the latched session does not serve the requested identity

## Scope

- `src/cadrumo/application/user_profile/_profile_record_repository.py`

## Description

- Re-derive the record authority when the latched session does not serve the
  identity being requested, rather than refusing.
- Cover the in-process profile switch that the one-command-per-process command
  line hides and a long-lived host does not.

## Outcome

The latched authority is now re-derived on identity mismatch. Before the change,
a second profile's every record read refused until the process restarted: a
command line that runs one command per process never sees this, while a
long-lived terminal or tool host sees nothing else.

Verified independently rather than accepted from the report: 13 passed in the
repository suite, sequential.

## Notes

The change also touched the shared capsule test helper, retiring the record
authority on both edges of the test session span. That is a shared surface with
many consumers, so the claim attached to it was challenged rather than accepted:
the helper's own documentation now states that reachability of a second profile
does NOT depend on either edge, because the production authority re-derives on
mismatch by itself. The retirement stands on the narrower and honest
justification that the span should zeroise the key material it unlocked, not on
a reachability claim the production fix already satisfies.

That distinction matters beyond this step. A test helper that must be adjusted
to accommodate a production change is sometimes evidence the production change
is incomplete; here it was not, but only because the helper's justification was
re-examined instead of being allowed to stand as written.

Two modules seeding through the shared helper remained red while this landed,
for an unrelated capsule-publication collision. They were confirmed not to be
caused by this change.
