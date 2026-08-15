---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
step_id: 'S134'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule what the destructive profile deletion surface should be, since both of its primitives have zero definitions anywhere in the tree

## Scope

- `src/cadrumo/application/config_reset.py and src/cadrumo/application/bucket_maintenance/`

## Description

- Establish whether the primitives were removed deliberately or lost as
  collateral, since that decides restoration versus first build.
- Re-point the consumers at the surviving surface.
- Stop at the retirement half if the supersession proves lossy.

## Outcome

**Deliberate replacement, not collateral loss** — established on three
independent signals rather than one. The primitives left in the capsule cutover
itself; the maintenance service's own docstring states that lifecycle mutation
moved to the custody transaction owner and that the old surfaces are
"intentionally not exposed here"; and the replacement exists and is exported, an
ordered, journalled, crash-resumable sequence covering both old primitives. A
re-pointing job rather than a first build.

The re-pointing landed. Both retired primitives are gone from the tests, and the
attribution is by cause rather than count: six failed and one passed on both
sides, but two import errors became two tests reaching real blockers. Same
total, different meaning — a claim only readable by attributing each failure.

One site deliberately keeps a raw directory removal, and the reason is recorded:
the guard under test is that a reset detects its target changing beneath it, so
a sanctioned deletion would prove nothing there — and is impossible anyway,
since that profile carries a filing the retention hold refuses.

**The retirement half is blocked, and the coverage check is what blocked it.**
Walking every field of the old contract against the new one — and one layer
above, in case the assessment was a lossy view of something richer — found the
retained-record count, the retention floor and the safe-erase date have no
successor at all. The newer preflight answers retention as two booleans.

Completing the retirement as scoped would mean either dropping those from a
persisted journal or populating them from a contract that cannot know the
answer, which means writing zero — **exactly the fail-open defect an earlier
step already closed**, whose row reads "a decision that blocks nothing and
reports zero retained records". The vault would have recorded a re-opened defect
as a supersession.

The loss is wider than the journal. Both fields are interpolated into a live
operator refusal, registered in the error registry, translated into all four
catalogues, and legally grounded — it cites Ley 58/2003 LGT arts. 66 and 70.
Narrowing it would render a statute-citing message as "Erase refused: 0 filed
tax records are still within the legal retention period": self-contradictory, in
four languages, on a surface whose authority comes from naming the law.

## Notes

The retention restoration is rowed separately as the precondition, with the
direction ruled — grow the contract rather than drop the fields, since the
filing retention authority already computes the position and the projection
discards it at the boundary. A narrowing to undo, not a capability to build.

**The re-pointing was also the instrument that exposed a live defect elsewhere.**
Moving a test onto the public facade removed a pinned clock, and without the pin
the sanctioned deletion path refused every time — a separate blocker, separately
rowed and since fixed. That is the second time in this step that doing the work
revealed more than inspecting it would have.

Whether the incomplete re-pointing was an abandonment or a deliberate halt at
this same gate could not be settled: no record exists either way. An unbooked
halt is indistinguishable from an abandonment, and that ambiguity is what made
this investigation necessary.
