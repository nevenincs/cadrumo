---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
step_id: 'S138'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make the delete hold guard compare the owner facts its docstring names rather than the whole assessment object

## Scope

- `src/cadrumo/application/user_profile/_custody_service.py`

## Description

- Narrow the guard's comparison to the owner dispositions it claims to test.
- State in code what still invalidates a confirmation, and what no longer does.
- Prove both directions: the false positive gone, the real hazard still caught.

## Outcome

No profile was deletable in production before this change, and the campaign's
closing destructive reset could not have run.

The guard required the hold assessment to remain current at execution and
enforced that with whole-object equality against a freshly assessed value. But
the assessment re-projects its observation instant and the digest attesting it
on every call, so only the legal and filing dispositions hold still. Preflight
and execution necessarily happen at different instants -- the operator must echo
a confirmation between them -- so the comparison failed every time, refusing
with "canonical legal or filing hold evidence changed after delete preflight"
when nothing had changed and no hold existed.

**The guard's own docstring named the right criterion while the code implemented
a different one.** It said a changed legal or filing owner FACT invalidates the
confirmation; the mechanism compared everything. That is the
criterion-versus-mechanism defect this campaign has catalogued in comments, in
an allowlist and in a governing constant, appearing here in executable code --
where it does not merely mislead a reader but refuses every deletion.

The comparison now tests the profile identity and the two owner dispositions.
What still invalidates a confirmation is stated in the code rather than in a
commit message: either owner flipping between cleared and held in EITHER
direction, and any current assessment that does not permit deletion. The
dangerous transition -- cleared at preflight, held at execution -- is caught
twice and independently, by the disposition comparison and by the permission
check.

**Both directions are proven, which is what makes the narrowing safe.** The
reproduction passes no pinned clock to any hop, so it runs on the wall clock
exactly as production does, and it reds when the whole-object comparison is
restored from outside the repository. The time-of-check/time-of-use test drives
the real legal-hold authority to open a case between preflight and execution and
still refuses -- and it passes under BOTH the old and the new comparison. That
two-sided result is the point: the false positive is gone and no false negative
was bought.

Twenty-nine custody-transaction tests pass. On the reset module the hold refusal
is gone entirely; the remaining failures are the retention gap already rowed and
one auth requirement, so deletion now passes this guard and stops at the next
real blocker.

## Notes

One residual gap is named in the docstring rather than left to be discovered: a
change of SOURCE RECORD under an unchanged disposition -- one legal case closing
as another opens, both held -- is not detected, because the assessment carries
dispositions and a time-varying digest rather than source-record identities.
Closing it needs the per-owner source digest carried in the journal, which is a
persisted-shape change and was not made. It is not a safety hole today: an
unchanged held still refuses, and an unchanged cleared is a state deletion is
legitimately permitted in.

**The re-pointing was the instrument rather than a side effect**, and that is the
transferable finding. The defect was invisible for exactly as long as the only
test driving the sequence reached past the public facade to the private
capability and pinned the clock on every call. Pinning is what made it pass, and
no production caller can pin -- the public facade exposes no such parameter.
Removing the pin by re-pointing the test onto the public facade is what exposed
it.

That argues for preferring public-facade tests as a DETECTION property rather
than as a style preference. A test that can reach a configuration production
cannot is not merely less realistic: it can conceal a defect that makes the
production path unusable, while reading as coverage of it.
