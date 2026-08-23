---
tags:
  - '#audit'
  - '#config-reset-recovery'
date: '2026-08-22'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:b424894ceef1f577e452396a1b930ad31ca8c7a47971b0128e296650905c1708'
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

## Resolved: resume at the post-erase boundary

The delete loop destroyed the capsule and only then advanced the phase and
saved. A crash in that window left a durable record saying the target was being
deleted while the capsule was already gone, and the loop's only skip was for a
target already marked deleted -- so a resume re-entered preparation, tried to
load a profile that no longer existed, and aborted. The reset was then
unresumable for good: the data erased, the operation unable to reach completion.

The loop now recognises a target whose erase already landed and advances it,
rather than re-driving a deletion against nothing. The check reuses the live
assessment the retention re-derivation already computes, and sits ahead of the
retention refusal: refusing on retention grounds is meaningless once the bytes
are gone. All thirteen durable boundaries now roll forward in a fresh process.

Absence alone does not authorise that advance. Absence is also what a capsule
destroyed by something else looks like, and claiming that as this reset's work
would be a false report in the one direction that matters. The deletion marker
written immediately before the erase is what distinguishes them.

Establishing that turned up something better than the guard: BOTH dimensions of
the marker's claim are already refused at the journal boundary, so a marker
naming another operation or another bucket cannot be persisted or loaded at all.
The attestation is structurally unforgeable rather than checked at the point of
use, which is the stronger place for it and means no downstream path has to
remember. The runtime check remains as defence in depth; its one reachable arm
is a marker that is absent entirely.

Stated rather than hidden: the completion time recorded is the resume's clock,
not the erase's. The instant the erase actually happened lives in the custody
delete receipt, which this operation cannot address because it does not record
the transaction id it started. That is a bounded imprecision; inventing an
earlier timestamp would be worse.

### What the three refused designs were worth

The fix is small, and it took three rejected designs to find, each refused for a
defect the previous had not considered. Trusting the custody receipt alone would
have reported a live profile as erased, because a receipt proves a transaction
finished, not that no capsule exists now, and republication reuses the identity.
Removing the carve-out that keeps a vanished target existing does not converge:
it raises, and forcing it through would discard the reset's own record that it
authorised the deletion. And pausing on a resurrected capsule self-cancels,
because the pause rebuilds the target and destroys the phase the guarantee is
predicated on.

None of that reasoning is wasted. Each refusal narrowed what a correct fix could
look like, and the design that survives is the one none of the three proposed:
recognise the landed erase, key the claim on the marker, and leave the exotic
resurrection case to the boundary that already refuses it.

## Resolved: the destruction path never released its file handles

The engine module documented, in two places, that the bucket-destruction path
disposes engines to release file handles before removing a bucket directory. No
such caller existed. The reset therefore renamed a capsule directory while the
same process still held its database open, which the platform refuses.

Both destruction sites now release first -- the rename and the removal, since a
handle can be reopened between them. Measured by neutralising the call from
outside the tree: four failures become one. The guard reads the source rather
than renaming a capsule, because a rename-succeeds assertion proves nothing on a
platform that tolerates an open handle, and those are exactly the platforms
where this stayed hidden.

Fixing it stopped it masking four further defects, each a different thing: a
removal helper holding its own handle while forging an external actor's removal;
two cases asserting a pause from persisting a filing, which does not move the
digest; a child that could not rename because the parent test process held the
database open; and a case left stale by a re-pointing onto a deletion primitive
with different semantics, whose expectations were never carried across.

## Open: a completed reset leaves a lockfile naming the profile it erased

Verified end to end through the operator surface. A reset that reports complete,
one profile deleted, removes the capsule directory and leaves
`.profile-custody-<uuid>.lock` beside it. The auth acquisition locks ARE cleared
-- the token directory is empty afterwards -- so this is specifically the custody
transaction lock.

Sized honestly: the file is zero bytes, so nothing about the profile's contents
survives. What survives is the filename, which carries the identifier of a
profile the operator was told had been erased. For a verb whose purpose is
removing local profiles, that is a completeness gap rather than a disclosure of
data, and it is worth neither more nor less than that.

Why it was left rather than fixed here. The lock path has no owner: it is built
inline where the lock is taken, and unlike the transaction, receipt and hold
directories it is not declared in the storage taxonomy -- which is plausibly why
nothing reaps it, since nothing else knows it exists. Reaping it is a design
choice with several defensible homes and one real hazard, the same one the auth
acquisition locks document: removing a lock another holder is about to take is
worse than leaving it. The safe shape is to reap only locks whose bucket no
longer exists, and only while holding the root lock that globally serialises
custody transactions, so nothing can be mid-flight. Choosing the home for that
-- the delete transaction's final act, the reset's completion, or a custody
maintenance verb -- is a decision, and inventing one on a destructive path at
the end of a long session is how the three refused designs above started.

## The suite cannot be trusted green while the tree is being written

A boundary case failed once in a long run and passed on re-run, which read as
flakiness in the reset. It is not. These cases spawn real child processes that
import the package fresh from disk, so a peer writing source mid-run can leave a
child importing a transiently inconsistent tree; it dies before any reset logic
executes. One bad window took out ten boundaries at once, which is what
distinguishes it from a code defect -- it is boundary- and order-independent.

The error names the wrong file, too: the missing symbol is resolved lazily
through the package facade, so the import machinery reports it against the
facade rather than the module actually being rewritten.

Two consequences. An authoritative run needs a quiet tree, or a detached
worktree pinned at a commit; a red result taken while peers are committing says
nothing about the code. And the harness now surfaces the resuming child's stderr
instead of its exit code alone -- that gap turned a one-look diagnosis into hours
of search twice, once for this and once for the defect above.

## Note on method

Each design was produced by one dispatched investigation and attacked by a second
with no shared context, and the attack earned its cost every time: it overturned
a scoping call of mine, a design of mine, a delivery decision of mine, and two of
the three rulings outright. The one-shot-pause defect surfaced only on the third
pass, after two designs had already been judged sound. Where a claim was
load-bearing the verifier ran it rather than arguing it, which is how the
fingerprint question was settled.
