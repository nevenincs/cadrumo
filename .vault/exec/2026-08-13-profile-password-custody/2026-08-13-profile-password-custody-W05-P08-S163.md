---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:b2a98a3f57d1d52f53b9500657bd0c7f79f2b824a8f70e1b001441daca515ef1'
step_id: 'S163'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh establish which side of the profile-record visibility split is lying, since the same record reads valid in the process that created it and reports missing_profile_record in a subprocess against the same storage root, and the evidence fits two incompatible readings — a record durably written but invisible across the boundary, or a record served from the creating process's cache and never durably written at all — the second being a custody defect of the first order that the first reading would conceal

## Scope

- `src/cadrumo/application/user_profile/ and src/cadrumo/adapters/persistence/`

## Description

- Create in one process, let it exit, read in a fresh one, so no cache can
  serve the answer.
- Inspect the storage root as bytes alongside the read, so the finding does not
  rest on any read path.
- Separate what the evidence establishes from what it merely permits.

## Outcome

**Neither candidate reading was correct, and the reassuring half is the one
that held: the profile record IS durably written.**

After the creating process exited, the storage root holds exactly one row in
the record namespace. The second row that had been counted earlier belongs to
the bucket event history -- a different namespace entirely, and a misread of a
table rather than a second record. So the catastrophic reading is refuted by
bytes on disk rather than by a read path that might itself have been lying.

**A fresh process nonetheless refuses that record**, with an integrity error
stating the capsule must contain exactly one current record row.

**The refusal misreports its own cause.** The check is a two-part condition:
the row count, and a comparison of the stored object key against a digest
computed for the profile. There is exactly one row, so the count half passes
and the failure must come from the key comparison -- yet the message describes
only the count. A reader following that message looks for a duplicate or a
missing row, and neither exists.

Computing the expected key at all raises an error demanding an active bucket
session, so the derivation is coupled to session state.

**The remaining question was whether the key digest VARIES between sessions
for the same bucket. It does not, and the severe reading is refuted.** The
subkey derivation states that it depends only on the data key and a stable
per-consumer context, and the data key belongs to the profile rather than to a
session. **So a session is needed only to REACH the key, not because the value
changes** -- a record is not unreadable by every process except its writer.

That was established by reading the derivation rather than by another probe,
after this step deliberately declined to assert between the two readings. The
refusal to guess is what made it cheap to settle.

**Both candidate defects are therefore closed: the record is durable, and the
digest does not drift.** Which makes the observed mismatch harder to explain
rather than easier, and leaves one hypothesis below.

## Notes

**The predecessor's conclusion was right and its reasoning could not have
established it**, which is a distinction worth keeping separate from being
wrong. That step read the record successfully in the process that had just
created it and concluded the record was durable. A cache serves that read
identically whether or not anything reached disk, so the experiment could not
discriminate -- and both readings predicted every observation it made,
including login and status succeeding while only the record read split.

**A probe that confirms a hypothesis in the environment that produced it is
precise about the wrong thing** -- the same shape as a census that measured
list literals mentioning a verb rather than calls to it, one layer up. The
correction cost one extra process and would not have been made by anyone
reading the earlier record, which is why the earlier record now carries the
correction inline rather than a footnote.

**Two custody diagnostics have now been found describing the wrong cause** --
a retired-artefact refusal that named the member but never the store, and this
one, which names a row count when the key is at fault. Both are accurate about
something true and misleading about what to do next, which is the failure mode
hardest to catch by reading.

**UNTESTED HYPOTHESIS -- labelled as such deliberately, because two readings
that fit every observation have already been wrong on this question, once for
each reader.** The custody secure-object repository opens a SHORT-LIVED STAGING
session before a capsule has been published, falling through to a temporary
session whenever the active one does not already serve that bucket. If the
record is written under the staging session's data key and later read under the
published capsule's, the digest cannot match -- deterministic given the key, and
the key differs. That fits every observation recorded here: durable bytes,
exactly one row, a failing key comparison, and a fresh process behaving
differently from the writer. **It has not been tested.** The direct test is to
compare the digest the staging path produces against the one the published path
produces for the same profile and object key.

**Outstanding regardless of how the cause resolves: the refusal message.** The
condition is a row count OR an object-key comparison, and only the count is
described. The count clause passes in every case observed here, so the message
names the half that is not failing. It cost two readers a hypothesis each, and
correcting it does not depend on diagnosing the mismatch.

**The durable lesson is the shared error rather than either finding.** Both
readers assumed one side of the boundary was lying -- that the record was never
written, or that the fresh process was simply wrong. Neither was. The record is
real AND the fresh process is right to refuse: it detects a genuine mismatch and
then misdescribes it. A disagreement between two components is not evidence that
one of them is broken.
