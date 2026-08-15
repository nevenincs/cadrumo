---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:61c5d2885b9b37274f47effd729fff69cf363e4a2b8c71eaced30251291641ba'
step_id: 'S173'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh distinguish an absent profile record from an absent session in the health projection, since a fresh process with no authenticated session raises a session-required refusal that the workflow state catches and converts to a null record, which the projection then reports as a missing record, so an operator whose profile is merely locked is told their record is gone, this being the false diagnostic that sent an earlier investigation hunting a durability defect that did not exist

## Scope

- `src/cadrumo/application/workflow/_models.py and src/cadrumo/application/workflow/_profile_health.py and src/cadrumo/application/user_profile/_profile_record_repository.py`

## Description

- Reproduce the false diagnostic end to end across two real processes before
  changing anything.
- Give the record read a typed reason so an absence stops being an
  undifferentiated null.
- Ask the lock question structurally, ahead of the reads the lock refuses.
- Route the locked verdict to the login action the profile already has.
- Prove both directions, and prove the gate bites in each.

## Outcome

**THE REPRODUCTION CAME FIRST AND IT FOUND TWO LIES, NOT ONE.** A child
process published a real capsule through the production lifecycle and exited;
a second process, holding no session, walked the chain. The session door
refused with the session-required message, the active-record resolver caught
exactly that and returned nothing, and the health projection reported the
record MISSING with an empty error field -- no reason carried at any layer.
The same process then opened the capsule with a real session and read the
record back at revision one with all fourteen facts: present, intact,
readable. The second lie was one call away. Reached without a supplied
workflow state, the identical profile reported the record UNREADABLE, because
the encrypted workflow state opens before the record and is locked by the very
same absent session. One benign locked profile, two different alarming
verdicts, decided by which caller asked.

**THE NULL NOW CARRIES ITS REASON, AND THERE ARE THREE OF THEM.** The record
read returns a resolution carrying either the record or one closed reason: the
selector resolves to no committed capsule, no authenticated session serves the
capsule, or a session is authenticated for a different identity. The reason is
a core enumeration beside the existing session-refusal one, so the three
layers that used to each re-derive an absence share one declaration. Exactly
one of the two fields is populated and the type refuses any other shape. The
convenience accessor that most callers use still collapses to a null and
needed no sweep; its docstring now says plainly that a caller REPORTING an
absence to an operator must not use it.

**THE LOCK IS ASKED STRUCTURALLY, NOT INFERRED FROM A MESSAGE.** The record
session door was split: resolution returns the authority or nothing, and the
refusing door is a thin wrapper over it. Nothing parses a refusal string to
learn whether a profile is locked. A malformed identity still raises rather
than returning nothing, because a caller defect must not read as a lock.

**ORDER IS THE FIX FOR THE SECOND LIE.** The projection asks the lock question
after the capsule projection and BEFORE the encrypted workflow state is
opened. Both entry points now agree, and a regression asserts they agree
rather than trusting that they do.

**THE REMEDY WAS ALREADY IN THE TREE.** A locked profile takes the shipped
logged-out session verdict: failed condition logged-in, action login, and the
name argument RESOLVED from the capsule label the assessment had already
resolved. So the operator is told which profile to log into, no new action was
invented, and no new operator sentence was authored -- there is no locale
change in this row at all. A lock is also not a broken pointer, so it offers
no pointer-clearing repair.

**AN EXISTING TAXONOMY MEMBER DID NOT COVER IT, AND THE HARNESS NEEDED
NOTHING.** None of the shipped statuses meant "intact but unread", so a new
one was added. The agent-facing readiness contract derives its accepted set
from the projection's own declaration rather than restating it, so the new
member was admitted without touching that tree, and its suite is green
unchanged. Measured on the locked capsule, the agent-facing readiness now
reports the lock.

**BOTH DIRECTIONS ARE PROVEN, ACROSS PROCESSES.** A new suite has a child
interpreter publish the capsule and exit. A locked profile reports locked and
routes to login. Both entry points agree. A real custody session reads the
same capsule through to ready -- the control, without which every locked
assertion would hold for a projection that said locked unconditionally. A
selector with no committed capsule keeps its own alarming verdict. And a
record row destroyed underneath a live session reports unreadable, because
with a session the absence is knowable and must be told.

**BOTH GATES WERE PROVEN TO BITE BY RUNTIME PATCH FROM OUTSIDE THE TREE.**
Making the projection never observe a lock -- the pre-fix behaviour -- reds
both locked cases, and they red as unreadable, which is the exact second lie
the reproduction measured. Making it observe a lock unconditionally reds the
ready control and the destroyed-record case. No tracked file was edited for
either.

**A SHIPPED TEST HAD PINNED THE ERASING FRAMING.** The resolution log
assertion named a message saying the read "returned no profile record". That
assertion now names the absence it actually observed, asserts the typed reason
beside it, and explicitly rejects the old wording so the framing cannot return
unnoticed.

## Notes

**Both gates were re-proven from a clean context, and the second proof taught
something the first did not.** Three runtime patches applied from outside the
tree, none touching a tracked file: neutralising the structural lock probe,
observing a lock unconditionally, and re-collapsing the carried reason onto the
absent-record status. The first reds both locked cases, the second reds the
ready control and the destroyed-record case, and the third reds the locked
cases. The instructive part is that the first proof MASKS the third on the
entry point that loads the encrypted workflow state -- that load is refused
before the collapsed reason is ever consulted, so the run reports unreadable
whichever way the reason is wired. Isolating the first lie therefore requires
the supplied-state entry point, which skips that load and reports the absent
record verbatim. That the two lies hide each other under measurement is exactly
why one of them survived the earlier investigation, and it is the reason both
entry points now carry their own assertion rather than one standing in for the
pair.

**Every downstream reader of the status set was audited, not just the one
already noted.** Two auth surfaces branch on the record-failure statuses -- the
operator's configure path and the certificate-source gate -- and both open the
encrypted workflow state BEFORE they consult the health verdict, so a locked
profile is refused by that load and never reaches their branches at all; their
behaviour is unchanged by this row and needs nothing. The diagnostics readiness
rows are the sole genuine fall-through, because they are the one place reached
with a health verdict and no loaded state.

**The CLI status surface was measured, not assumed, and it did not regress.**
Run against a locked capsule, it refuses before reaching the projection's
fall-through and prints the logged-out sentence with the login action and the
profile name -- the same condition and action the projection now produces.
That agreement was the reason to reuse the session verdict rather than mint a
record-repair one.

**One downstream surface is left wrong and is reported rather than taken.**
The diagnostics readiness row keys off two status sets the new member is not
in, so a locked profile falls through to the "no profile configured" summary.
It still warns, so nothing is silently passed, but the sentence is untrue.
Correcting it needs a new operator string in all four catalogues, which this
row may not author, and the row belongs to that surface's owner.

**Peers' broad commits captured this working tree mid-row, repeatedly.** Every
file this row touched was swept into registry-sweep commits that were not this
row's, spread across six of them rather than one, so the change is committed but
its history is scattered and none of it carries this row's subject. The
verification pass therefore had to re-derive what had landed by reading the
tree rather than by reading a diff. Nothing was committed, stashed or reverted
here.

**The suites were re-run sequentially and their red is attributed, none of it
from this change.** The one failure that WAS from this change -- the pinned log
assertion -- is corrected above and passes. The rest lands in five ambient
families: registry validation failures from a concurrent authority-grade sweep;
a shared capsule-seeding harness that no longer publishes a capsule the
committed-capsule projection discovers, which accounts for every error in the
resume suite and for the empty-projection assertion; CLI verbs and a wizard
creation door that are settled absences; a profile-registration helper whose
signature changed underneath its callers; and, arriving mid-run, a peer's new
custody error class landing without its error-code registry entry, which now
fails the resume suite at import rather than at assertion. That last one is the
tree moving underneath the run, and the refusal says so itself. The row's own
surfaces -- the cross-process locked-profile suite, the resolution suite whose
log framing this row corrected, and the health projection suite -- are green
together, as is the agent-facing readiness taxonomy, which admitted the new
member with no edit to that tree.

**The durable lesson is that a null is a decision to discard evidence.** The
resolver had the reason in its hands -- it caught a specific typed refusal and
threw the type away. Every layer above then had to guess, and the guess became
an assertion about a taxpayer's financial records. The cheapest defence is
that a boundary reporting an absence must carry why, and the tell here was an
error field arriving empty on a verdict that claimed data was gone.
