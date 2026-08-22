---
tags:
  - '#audit'
  - '#config-reset-recovery'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:47df5e359693d8a6773bfcb8c656e80519ed73ccb66d92363080471e12997cc3'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
---

# `config-reset-recovery` audit: `delete idempotency findings`

## Scope

Why a crashed all-profile reset cannot resume at the post-erase boundary, and why
three successive designs to fix it were each refused. Every claim below was read
at source and the decisive ones were executed. Two defects found on the way are
fixed and shipped; the third is recorded here unfixed, deliberately.

## Delivered

**The retention override now reaches the custody transaction.** The operator flag
was accepted, journalled and honoured at both preflights, then dropped before the
one step it authorises, so a reset that legitimately approved an override could
never complete. The filing half of the custody hold IS the statutory retention
floor - both sides compute from one floor assessment - and the reset's own
backstop had always let a recorded override past, so the custody gate was
silently refusing the very fact the operator acknowledged. One decision function
now answers the hold question for both custody gates; the raw owner property
stays override-blind so the evidence record keeps attesting that a hold existed
and was overridden.

Stated plainly because it is a real reduction: an operator can now unrecoverably
destroy filed records inside the four-year window on their own recorded
authorisation. A legal hold remains absolute - though that guard is currently
unoccupied, since no production path records an open case.

**A stale authorisation could reach the destructive step.** A target that reaches
the deleting phase is skipped by the auth-clearing sweep, so it carried whatever
retention decision the snapshot recorded, and the hold decision weighs the
override as a boolean without comparing counts. An override approved against two
retained filings would have cleared a hold covering fifty. Retention is now
re-derived against a live assessment before anything reads it.

**The reset-level tamper detector had no proof.** The case named for it perturbed
a filing, which does not move the digest - it lands in the database, covered by
path only, and in a snapshot outside the capsule. The replacement plants a
foreign file, leaving the capsule parsing cleanly, so nothing but the digest
comparison can be what refuses it.

## Recorded unfixed: resume at the post-erase boundary

Three designs, three refusals, each for a defect the previous had not considered.

**Evidence alone lies.** A delete receipt proves a transaction finished, not that
no capsule exists now, and republication reuses the identity. Trusting it would
report a live profile as erased.

**Absence alone does not converge.** Removing the carve-out that holds the target
existing does not fall through to completion; it raises, two ways, and forcing it
through would discard the reset's own record that it authorised the deletion.
That carve-out is also what keeps the target counted honestly.

**The pause self-cancels.** With the operator ruling that a resurrected capsule
must pause rather than be erased, the pause rebuilds the target from a fresh
assessment - dropping the marker and the phase the invariant is predicated on. The
next confirmed resume sees an ordinary profile, mints a fresh transaction, and
erases it. The guarantee holds for exactly one resume. Any workable design must
key the check on the bucket carrying a completed delete receipt rather than on the
phase, or persist something the rebuild does not drop.

Two further facts a future attempt needs. A restored capsule can never be
fingerprint-identical, because the commit record mints a fresh transaction id and
publication instant and the inventory covers records by content - verified by
running a real create and restore and diffing the digests, where that single
300-byte file was the only delta. Nothing pins that record into the covered set,
so an exclusion added for a defensible reason would silently reopen the hole. And
there is no behavioural test anywhere of resuming a deleting target whose capsule
is still present, so claims that the present-capsule path is already covered are
close to vacuous.

## Recorded unfixed: the destruction path never releases its file handles

The engine module documents that the bucket-destruction path disposes engines to
release handles before removing a bucket directory. No such caller exists; the
only disposal happens inside session close. The reset therefore renames a capsule
whose database the same process may still hold open.

This is the root cause of five failures in the reset suite, each dying on a
directory rename. It reads as environmental and is not: it bites hardest where
the platform refuses the rename, and would stay hidden where the platform allows
it. Any long-lived process driving a reset carries the same exposure. Fixing it
introduces a dependency from the custody adapter onto the engine layer on a
destructive path, which is why it is recorded rather than patched here.

## Note on method

Each design was produced by one dispatched investigation and attacked by a second
with no shared context, and the attack earned its cost every time: it overturned
a scoping call of mine, a design of mine, a delivery decision of mine, and two of
the three rulings outright. The one-shot-pause defect surfaced only on the third
pass, after two designs had already been judged sound. Where a claim was
load-bearing the verifier ran it rather than arguing it, which is how the
fingerprint question was settled.
