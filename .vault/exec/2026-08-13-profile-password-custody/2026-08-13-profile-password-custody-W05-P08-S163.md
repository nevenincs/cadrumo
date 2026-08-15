---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:5162d09d1e00855e492b2349f8b1a48e33901383cc60fa962e0b685b1eca7903'
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

**What this does NOT establish, and must not be read as establishing:**
whether the key digest actually VARIES between sessions for the same bucket.
If it does, a record is unreadable by any process except the one that wrote
it, which is severe. If the derivation merely needs a session in order to be
computed -- because it descends from the bucket key, which is stable -- the
mismatch has some other cause. The evidence separates the durability question
and does not separate this one.

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
