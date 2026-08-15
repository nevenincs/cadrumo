---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:90a40a0b6d5a15d6d47d95b5f93fe5a177c74a0f3840b7387b8c9726ef089765'
step_id: 'S120'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh repair the rotation crash-window test module broken at HEAD, which imports a keystore filename constant whose definition the deletion removed and which it is now the only referent of, this being a collection error that can abort a whole run rather than a single failing test

## Scope

- `src/cadrumo/adapters/persistence/storage/tests/test_rotation_crash_windows.py`

## Description

- Close this row as superseded, and carry its remaining work forward under a
  row that describes it honestly.

## Outcome

**Superseded before it was worked.** The row was opened to repair a module
broken at HEAD; roughly an hour before the instruction reached its intended
owner, that owner had already deleted the module whole to unblock collection.
So this row pointed at a file that no longer exists, and would have sent
whoever picked it up looking for it.

The deletion was the right call and the reason is structural rather than
expedient. The module injected crashes into a mixed-key rotation across three
stores, and its single fixture seeded all three, so the keystore was not an arm
that could be amputated -- it was the fixture. Deleting the module unblocked the
storage package immediately; a partial rewrite could not have been verified
while the package did not import.

**What matters is that the loss was booked rather than passed off as cleanup.**
Two subjects went with the module and both still have a real subject against the
two surviving stores: the crash window between envelope and blob-store rotation,
and the probe-skip idempotency that makes re-running a partial rotation a clean
no-op. Those are carried forward as a reconstruction row that names them
explicitly.

That naming is the whole point of closing this row this way. A deletion whose
losses are recorded is a decision; the same deletion with the row quietly closed
is coverage disappearing silently, which is worse than either keeping the module
or replacing it.

## Notes

The row was opened against a measurement that was accurate when taken and stale
by the time it was acted on -- the third instance of that shape in one hour, and
the third distinct diagnosis of a single symptom. Two agents and the team lead
each named a different cause for the same broken lane; each was correct when
measured and superseded before the instruction landed.

The durable form: on a tree with several concurrent writers, **re-measure a
failure cause at the moment of acting on it rather than at the moment of being
told it** -- including when the instruction comes from the team lead. A cause
that arrives in a message has already aged.
