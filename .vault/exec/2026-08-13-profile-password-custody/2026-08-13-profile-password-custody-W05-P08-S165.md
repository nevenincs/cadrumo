---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:20205f2f467d23f4889cca6ff92b90fc660f2f4e72dade0c1d1472cf12758827'
step_id: 'S165'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh establish why a durably written profile record fails its object-key comparison in a fresh process when the digest is deterministic given the DEK, testing first whether the record is written under the short-lived staging session the capsule repository opens before a capsule is published and therefore keyed under a digest the later published session cannot reproduce, and correct the refusal message which reports only the count half of a two-part condition while the key half is what fails

## Scope

- `src/cadrumo/application/profile_custody/ and src/cadrumo/application/user_profile/_capsule_record.py`

## Description

- Measure the stored object key and the key a fresh process derives, side by
  side, before reasoning about either.
- Split the two-part admission condition so each half reports itself.
- Carry the measurement into the suite as a cross-process proof.

## Outcome

**THE MEASUREMENT CAME FIRST AND IT SETTLES THE ROW. The two keys are the
same bytes.** One process created a profile through the real credential door
and exited; a second, fresh process unwrapped the committed envelope and
derived the key for the same profile. The digest the writer stored and the
digest the reader derived are byte-identical, and the data-key fingerprints
on both sides match. Nothing diverges -- not the key, not the DEK, not the
namespace, not the encoding.

**THE STAGING-SESSION HYPOTHESIS IS REFUTED.** Reading the staging path after
the measurement shows why it could never have held: the temporary session the
capsule repository opens before publication is bound to the record session's
OWN data key -- the same 32 bytes the envelope wraps and a later login
unwraps. The subkey the digest is HMAC-ed under depends on that key and a
stable per-consumer context and on nothing else, so the staging and published
sides derive identically by construction. The hypothesis was well-formed and
fitted every recorded observation; it was simply wrong, and one measurement
was cheaper than the reasoning that would have argued it either way.

**THE PREMISE ITSELF DOES NOT REPRODUCE ON CURRENT HEAD.** The production
read succeeds cold: a fresh process loads the record through the real store,
and the real CLI profile-show command reads the same record in yet another
process and reports it valid-but-incomplete. So the invisible-record symptom
is not a live defect of the key comparison.

**WHAT DOES PRODUCE THE OBSERVED SYMPTOM IS A DIFFERENT FALSE DIAGNOSTIC,
ONE LAYER UP.** Measured directly: a process with no live custody session for
the profile gets a refusal saying profile facts require an authenticated
session, the active-record resolver catches exactly that refusal and returns
nothing, and the health projection turns nothing into a missing-record
status. The record is present and readable; what is absent is the session.
That is the mechanism behind the earlier subprocess observation, and it is
addressed below rather than here.

**THE REFUSAL MESSAGE IS CORRECTED AND LANDED, INDEPENDENT OF THE CAUSE.**
The admission test was one combined condition -- a row count and an
object-key comparison -- reported by a single message naming only the count.
It is now two conditions, each reporting itself: the count refusal states the
count it observed, and the key refusal says the capsule holds one row
addressed to a different object key, naming both causes a divergence can
have. A hard refusal stays an exception rather than moving to the notice
channel, which is the non-blocking advisory spine.

**A SHIPPED TEST HAD PINNED THE FALSE DIAGNOSTIC.** The restore refusal for a
database bound to a different profile UUID asserted on the count wording --
in the exact case where the count is right and the key is wrong. That
assertion is now the truthful one, and it explicitly rejects the count
wording so the old message cannot return unnoticed.

**THE PROOF SPANS REAL PROCESSES.** A new suite has a child interpreter
publish the capsule and drive its replacement, then exit; this process opens
it cold and asserts strict equality, that no defaultable field sits at its
default after the crossing, and that the stored key equals the key derived
here. Two anti-tautology proofs corrupt the persisted bytes -- one per half
of the admission test -- and require the cold load to refuse.

**BOTH GATES WERE PROVEN TO BITE, BY RUNTIME PATCH FROM OUTSIDE THE TREE.**
Making the digest process-scoped -- exactly the shape the refuted hypothesis
predicted -- reds three cross-process cases including the key measurement.
Restoring the pre-fix count-only refusal reds both corrected-diagnostic
assertions. No tracked file was edited for either.

## Notes

**Nothing in key derivation was touched, and that was the right outcome
rather than caution.** The measurement showed the derivation is already
stable across the boundary, so a change there would have been a fix for a
defect that does not exist, with encrypted data at stake.

**What was NOT done, deliberately:** the missing-record status that this row
was written around is produced by the active-record resolver swallowing an
authentication refusal into an absent record, in the workflow projection and
the record repository. Correcting it means distinguishing record-absent from
session-absent at that boundary, which is a different owner's files and a
different row. It is reported rather than taken.

**Two live defects were observed in passing and belong to others.** The CLI
status command crashes on an orphan mounted-family declaration for a config
passphrase family, which the refusal projection then hits again while
building its own error. And the record-session refusal path reports through a
status whose name asserts something untrue about storage.

**A suite-wide run shows fourteen failures in this package, none of them from
this change.** They are a retired wizard door, renamed CLI verbs, a helper
signature changed underneath its callers, a login handover journal refusal,
and a registry source-reference validation that a concurrent sweep landed
mid-run. The record boundary itself is green, including under a serial
re-run.

**The durable lesson is that the row's own framing was the most expensive
assumption in it.** Three readers in a row proposed a mechanism that fitted
every observation, and each was wrong; the difference here was spending one
measurement before the first sentence of explanation. The fixture that could
not fail was the tell each time -- a probe run in the process that produced
the condition, then a hypothesis about a boundary that was never crossed.
