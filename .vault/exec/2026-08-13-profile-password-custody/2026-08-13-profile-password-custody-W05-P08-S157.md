---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:c0882f50e3b7946560f7d4579daa2348654f9dae68f53ed68082b44bc6537f84'
step_id: 'S157'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh write an empty filing catalogue snapshot at profile creation so that never-filed is a recorded fact rather than an absent one

## Scope

- `src/cadrumo/application/user_profile/_registration.py`
- `src/cadrumo/application/filing/_profile_filing_retention.py`
- `src/cadrumo/application/modelo/_revision_persistence.py`

## Description

- Record an empty filing snapshot when a profile is created.
- Give both snapshot writers one shared best-effort recorder instead of two copies.
- Prove a recorded-empty snapshot and an absent one stay distinguishable.

## Outcome

Absence and emptiness were the same observable, and they are not the same
fact. A profile that had never filed and one whose snapshot write had failed
both left no snapshot, so the retention assessment refused identically for
both and blocked deletion for an opaque reason. Creation now records an empty
snapshot, which makes "this profile has filed nothing" an answer the filing
owner gave rather than a question nobody asked.

**Keeping the two states apart is the deliverable, not the empty snapshot.**
The snapshot writes are permitted to be best-effort ONLY because absence fails
closed: with no snapshot the assessment refuses, which blocks a deletion rather
than permitting one. Had this step resolved the ambiguity the other way -- by
treating absence as nothing-retained -- every swallowed write would have become
a fail-open on the erasure of taxpayer data. The test therefore asserts the
distinction directly, refusal on absence and a real assessment on a recorded
empty, in one test so the two cannot quietly converge, and it fails when
absence is made to degrade into an empty result.

**Both writers now share one recorder, and that is a smaller change than the
diff suggests.** Duplicating the swallow at a second call site would have
created two copies of one safety argument, and copies drift: the second writer
would eventually have carried a stale version of the reason it is allowed to
fail silently. The recorder carries the argument in its docstring -- the
asymmetry that neither caller exists to serve deletion, one creating a profile
and one discharging a statutory filing obligation, so refusing either for a
deletion-support record is worse than a missing snapshot that merely fails
closed later. Collapsing the filing-time duplicate also removed the two imports
that existed only to serve the copy.

## Notes

**Three decisions now rest on one invariant, and a reader who weakens it must
find all three.** The invariant is that an absent retention snapshot fails
CLOSED. Resting on it are: the filing-time write being allowed to fail
silently, the creation-time write being allowed to fail silently, and this
step's choice to leave absence meaningful rather than defaulting it. The
recorder's docstring names the revisit condition, but the coupling is stated
here because it spans three sites and no single docstring is the natural home
for it.

**All production callers ignore the recorder's boolean**, so a failed snapshot
write is invisible in production outside the warning log. That is sound only
because of the same invariant: the consequence of a missed write is a later
refusal, not a permitted deletion. The return value exists so a caller's tests
can assert the write happened rather than inferring it from a side effect, and
if the invariant ever inverts, this silence becomes the third thing to revisit.

The registration path's own suite is integration-marked. A first run of it
contributed zero tests while reporting success for the tests that did run,
which is the marker-deselection shape this campaign has been caught by before;
re-run under the integration marker it is fifteen passing.

No backfill was written. Profiles created before this step simply have no
snapshot, which pre-release is fine and which the fail-closed invariant makes
safe rather than merely tolerable.
