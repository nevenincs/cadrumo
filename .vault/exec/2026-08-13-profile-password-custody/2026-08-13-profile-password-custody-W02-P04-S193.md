---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:a341793ea3803381b68ab5400315d4267deadff6bd7b6c8c50d7bfda64c67b10'
step_id: 'S193'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh retire the displaced profile's session material inside the registration transaction itself, since registration selects the new profile by pointer compare-and-swap and retires nothing, so the previously active profile keeps a resumable acceleration receipt until some later login happens to observe the boundary, leaving its bucket key recoverable with no passphrase across the whole window and permanently for a registration no login ever follows, which is the same leak the handover revocation was rebuilt to close reached through the creation door instead

## Scope

- `src/cadrumo/application/user_profile/_custody_service.py and src/cadrumo/application/user_profile/_registration.py`

## Description

## Outcome

## Notes
