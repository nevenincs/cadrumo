---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:19db0c77aade3e4d70c70b55d7488ceefb0278e50f21b9f698ea61fcfb4232f1'
step_id: 'S81'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh revoke the retired profile's session material on the durable pointer unioned with the live session

## Scope

- `src/cadrumo/application/user_profile/_login_session.py`

## Description

- Derive the profile to retire from every source that can name it, rather than
  from the live in-process session alone.
- Preserve the guard that prevents revoking on a same-profile re-login.
- Prove the property across process boundaries rather than within one process.

## Outcome

**The campaign's most serious defect is closed.** The handover derived the
profile to retire solely from the live in-process session, and every command-line
invocation is a fresh process, so in the ordinary operator flow that value was
empty, the revocation gate never fired, and the retired profile's thirty-two byte
bucket key remained recoverable with no passphrase. Four of the five crash phases
leaked identically, because recovery also always runs in a new process.

The fix folds **three** observations, and the third was not in the brief. The
dispatcher specified two -- the live session and the durable pointer -- reasoning
from the logout path, which unions exactly those. The implementation found that
neither is complete during a replay: an interrupted handover being replayed has
already moved the durable pointer on to the incoming profile, so the pointer no
longer names the profile being retired, and the interrupted-handover record is
the only remaining source. A fix built to the brief would have closed the
ordinary flow and left the replay path leaking, which is precisely the case where
the original defect was worst.

The guard distinguishing a genuine handover from a same-profile re-login is
preserved. That guard is load-bearing rather than defensive: on a re-login the
profile is unchanged, and revoking there would destroy the receipt the very login
just minted.

Verified independently: the handover suite is 28 passed.

## Notes

The defect existed because an earlier fix in this campaign closed only half of
it. That fix was correct for the in-process case and was verified by a test that
ran both logins in ONE process -- the single configuration in which it worked. It
verified the property exactly where its precondition held, which is this
campaign's signature defect appearing inside a proof rather than inside code.

The dispatcher approved that earlier fix and set its verification conditions,
requiring the regression to assert on recovered key material rather than on a
vanished file. It did so. The condition was met and the defect survived, because
the condition governed WHAT was asserted and never questioned the process
topology it was asserted in.

Two traps were marked in advance and neither was rediscovered: the handover
journal's stored identity is populated from the same live-session value and is
therefore empty in exactly the failing cases, and the change-of-bucket guard had
to survive the widening of its input.
