---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:a668fdba5666d6d72381b176ab9ca7f5161fbf2ebe23c0445f3e774571b0952b'
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

Three further facts arrived after this record was first written, none of which
the dispatcher's brief had anticipated.

**The activated crash phase does not pass through promotion at all.** Recovery
classifies an activated handover as complete, clears the journal, and the next
login takes the idempotent no-op and returns BEFORE promotion runs -- so no
widening of the promotion path could reach it, and it continued to leak after the
union fix. Retiring there is a pure durable delete needing no authentication, and
it is now completed at recovery classification, routed through the same single
revocation authority rather than a second one. Measured: without it, that phase
still leaked.

**The handover journal becomes a valid source only once the retirement identity
is fixed.** The dispatcher marked the journal unusable because it was populated
from the same live-session value and was therefore empty in exactly the failing
cases. That was true of the journal AS IT STOOD and stops being true once the
identity is corrected, so the implementation also populates it from the same
durable-first union -- without which a crash in a fresh process leaves the replay
path with no source at all.

**The union fold is SHARED with logout rather than mirrored.** Logout now calls
the same fold, replacing its inline construction over the same two values, so no
second revocation path exists.

The finding recorded against the crash parametrisation as merely flaky was closed
and proved worse than flaky. At one phase the receipt was already gone, meaning
the watcher had observed the phase but the handover ran to COMPLETION before the
process exit landed -- the window being the watcher's own write of the observed
phase, a filesystem write on this share. That case was intermittently a test
named for a crash that never happened, with the retirement silently running and
the test passing for the wrong reason. The observation now rides on the exit
status and the process dies on the instruction after the comparison.

The bite proof reproduces the independent review's measurement exactly: reverting
both fixes yields five failures against twenty-three passes, every failure on
recovered key material, four of five phases leaking and the already-retired phase
clean. The first injection attempt reddened on the reported outcome rather than
the material and was reordered so the material is measured first.

**The decision record already specified this, so the defect was implementation
drift from a written contract rather than an unspecified area.** The governing
rollup record states that success atomically swaps the active reference, promotes
the incoming session, attempts optional keyring acceleration, cleans candidate
artefacts, and only then retires the prior profile. It says RETIRE A -- A being
the profile the handover moved away from -- and never says that identity comes
from the live session. The live-session-only derivation was the implementation
drifting away from the contract, not the contract failing to say.

That also settles the standing of the second fix, which the dispatcher's brief
had not anticipated. The same record assigns stale-session revocation to login's
mandatory custody-transaction preflight, which is exactly where the
recovery-time retirement was placed. It is therefore on-contract rather than an
invention, which could not have been claimed from the code alone.

A third clause is consistent rather than contradictory: custody-generation
changes revoke sessions, and a handover changes neither generation nor key epoch
-- which is precisely why the receipt survives and explicit retirement is
load-bearing.

**The overloaded-vocabulary warning paid off here, and would otherwise have
prevented the complete fix.** This step touches the profile-session acceleration
receipt, which lives in the keystore sidecar OUTSIDE the encrypted bucket store,
so revoking it needs no unlocked profile -- measured, by the recovery-time
retirement running before any authentication and the previously-leaking phase
passing. The sibling finding that revocation requires an unlocked profile is
correct about the OTHER artefact, the authority session held as an encrypted row
inside the bucket. Carrying that correct finding across the name would have
concluded that recovery-time retirement was impossible and left the phase
leaking.

An exhaustive sweep found no third site. All six durable teardowns of
profile-session material in production now resolve identity from a durable
source, and every call site of the live-session accessor was read: the
non-revocation ones are liveness guards for the idempotent-login no-op rather
than identity derivations, and the one live-session-only revocation is so BY
DESIGN, because it zeroises this process's key material and must not reach
another profile.
