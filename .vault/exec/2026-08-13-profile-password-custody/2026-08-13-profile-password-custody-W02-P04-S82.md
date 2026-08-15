---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:4633463241bbf587d61899b20799e371cfdc5e042c08ff98f26eb419fbfd666c'
step_id: 'S82'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh re-site the non-resurrection proof across separate processes

## Scope

- `src/cadrumo/application/user_profile/tests/test_login_handover.py`

## Description

- Move the non-resurrection proof out of the single-process configuration in
  which the incomplete fix worked.
- Extend it over the crash parametrisation, where recovery always runs in a new
  process.
- Keep the assertion on recovered key material rather than on file absence.

## Outcome

The proof now runs across process boundaries, which is the configuration the
defect lived in. The previous test was well built in every respect except
topology: it asserted on recovered material rather than on a vanished file, and
it carried a genuine anti-tautology arm proving the receipt IS resumable while
the profile is live. But it ran both logins in one process, so it could not fail
on a defect that only manifests when no session is live -- it verified the
property precisely where the precondition held.

A companion case pins the opposite direction: a same-profile re-login in a NEW
process must KEEP its own session material. That is the guard the widening could
most easily have broken, and without it a fix that revoked unconditionally would
satisfy the resurrection test while destroying the receipt each login had just
minted.

Verified independently: 28 passed.

## Notes

The lesson generalises past this suite and is the most transferable thing the
campaign produced. A proof inherits the environment it is written in, and a
single-process test of a property that only breaks across processes is not a weak
test -- it is a test of a different property that happens to share a name. No
amount of care about WHAT is asserted repairs an assertion made in the wrong
configuration.

The dispatcher's verification conditions on the earlier fix were satisfied in
full and did not catch this, because they governed the assertion's content rather
than its setting. That is worth recording as a limit of review: reading a test
for what it asserts is not the same as asking which configurations it can fail
in.
