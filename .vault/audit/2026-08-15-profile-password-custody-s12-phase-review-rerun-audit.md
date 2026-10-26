---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:079751496965e14ca83311517ae2a4b535e11ac11dd3311cc1f22e86c8e68317'
related: []
---

# `profile-password-custody` audit: `s12 phase review rerun`

## Scope

Fresh-context re-run of the login and session handover phase review, dispatched
after all three re-closure conditions from the first review appeared to be met.
The reviewer was given the dispatcher's measurements explicitly flagged as
possibly stale, and told that refusing to close with reasons was a better outcome
than a closure needing reversal. Verdict: **FAIL, the step cannot close.**

All three conditions ARE met, and each was re-verified independently. The blocker
is the step's own central property.

## Findings

### s12-handover-retires-only-the-in-process-profile | critical | The retired profile survives in the ordinary operator flow

The handover derives the profile to retire SOLELY from the live in-process
session. That value gates the revocation added earlier in this campaign to close
the resurrection hole. **Every command-line invocation is a fresh process**, so
in the ordinary flow no session is live, the derived identity is empty, the gate
never fires, and revocation never runs.

Confirmed independently in the source: the promotion path reads the current
bucket session and takes its identity, while the logout path five hundred lines
above in the same file does it correctly -- it unions the live session with the
durable pointer read inside the pointer transaction and revokes every resulting
identity. Logout gets the multi-process case right; the handover does not.

Measured on recovered key material rather than on file absence, across two real
processes: the retired profile's receipt is present and resumes, returning its
thirty-two byte bucket key with **no passphrase** -- verbatim what the function's
own documentation claims to refuse. Four of the five crash phases leak
identically; only the phase whose retirement completed before the crash is clean.
One root cause throughout, because recovery also always runs in a new process.

The obvious alternative source is foreclosed: the handover journal's stored
identity is populated from the same live-session value, so it is absent in
exactly the failing cases. The durable pointer already carries the retired
identity in every process and is the correct source.

**Why the existing proof missed it.** The non-resurrection test is well built --
it asserts on recovered material, not on a vanished file, and carries a genuine
anti-tautology arm proving the receipt IS resumable while the profile is live.
But it runs both logins in ONE process, which is the single configuration where
the revocation works. It verifies the property only where the precondition holds,
and therefore cannot fail on this defect. That is this campaign's signature
defect -- an operation reporting success when its precondition is false -- in a
new register, and this time inside the proof rather than the code.

### s12-crash-phase-parametrisation-is-flaky | medium | An intermittent gate trains readers to re-run

One crash-phase case failed once in four sequential runs. The reviewer traced the
classification through control flow before running it and confirmed the split is
genuine production self-consistency rather than a test relaxed to fit: pre-
activation phases replay in full and retain a terminal receipt, terminal phases
take the idempotent no-op and write no journal. The flake is a race inside the
crash injection itself, where a watcher thread polls and exits while the main
thread can advance in between. Carry-forward, but worth closing, because an
intermittently red gate trains readers to re-run rather than investigate.

## Recommendations

Revoke on the durable pointer unioned with the live session, mirroring the logout
path in the same file. Then re-site the non-resurrection proof across SEPARATE
processes and extend it over the crash parametrisation, because the current
single-process shape cannot fail on this defect.

Do not close the step. The three conditions are genuinely satisfied and that work
is real, but the property the step exists to guarantee is measurably false in the
flow operators actually use. A third closure on a property that does not hold
would be considerably worse than leaving the row open.

One correction the review supplied to the dispatcher: the absence gate is GREEN,
not red. A dispatcher measurement of two stale declarations was accurate when
taken and went stale mid-review, because a peer landed the declaration update in
between. That landing carried its own security repair worth recording -- a health
report had been entering the shared-master provider to unlock a taxpayer's bucket
with no password so it could print, and that is now removed.
