---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:cae7e0e061765f96a143da42d0e68836a53c5aff65aacbdf7c7bd62249e72cc7'
step_id: 'S155'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh have the filing persistence path record the retention snapshot at the moment a revision is filed

## Scope

- `src/cadrumo/application/modelo/_revision_persistence.py`
- `src/cadrumo/domain/retention/_errors.py`

## Description

- Record the filing catalogue into the retention snapshot after a filing durably saves.
- Make that write incapable of failing the filing it follows.
- Prove the assessment moves from refusing to answering, and that a failing write is survived.
- Correct two overstated claims about the original deferral.

## Outcome

The retention snapshot now has a producer, and the deletion preflight can
assess a profile that has filed.

**The producer had to move, and establishing why is most of this step.** The
row was first scoped to refresh the snapshot at the deletion preflight. That is
not available: a reset holds locks on targets it has not unlocked, and the
filing catalogue lives in the bucket's encrypted store, so at the moment the
preflight runs the records are under a key nobody holds. The filing path is the
only moment both conditions hold at once -- the retention position changes
there, and a session for that bucket is held by construction.

**The decision in this step is the failure mode, not the hook.** The write runs
after the catalogue has durably saved, and any failure is logged and swallowed,
so it can never fail a filing. The asymmetry is the whole argument: a filing
that succeeded with a stale snapshot is recoverable, while a filing REFUSED
because a deletion-support record could not be written is not, and it would be
this campaign obstructing a statutory obligation to serve its own concern.

Swallowing is defensible only because the downstream failure is fail-CLOSED. A
missing snapshot makes the retention assessment refuse, which blocks a deletion
rather than permitting one. The docstring records both halves together, and
names the condition that would invalidate the pairing: if an absent snapshot
ever comes to mean "nothing retained", the swallow becomes a fail-open and must
be revisited with it. The two decisions are safe only in combination, which is
why they are documented in one place rather than two.

Both properties are proven rather than asserted. The first test shows the
assessment moving from raising to reporting a real retained record. The second
drives a GENUINE failure -- a bucket identifier that is not a canonical UUID --
rather than a simulated one, and removing the swallow at runtime fails exactly
that test while the other stays green, so the test proves the protection rather
than that a function was called.

## Notes

**Two overstatements were corrected, one of them in this campaign's own
records.** An earlier step claimed the original deferral -- that retention
requires decrypting the profile record under an authenticated session -- was
obsolete. It is half obsolete: ASSESSING needs no session because the snapshot
is plaintext, but PRODUCING that snapshot still does, exactly as the deferral
said. The snapshot relocates the requirement to the write side rather than
abolishing it. Both the error docstring and the earlier step record now say the
precise thing, and the record states that its first version overstated it --
one document above the warning it exists to give.

**A phantom cycle-break was removed.** Both imports in the new function were
written function-local in a module that imports everything else at module
level, which reads as a cycle break and invites the next reader to design
around an edge that does not exist. There is no edge: `application.filing` does
not import `application.modelo` at all, and every apparent match resolves to
`domain.modelos` or to a locally defined symbol containing the word. Hoisted,
and both packages verified to import standalone afterwards.

The originating row names a scope path under the calculations package; the
filing persistence writer actually lives under the modelo package, and the
scope above records where the work landed.

The wider filing-persistence suite could not be used to attribute this change.
It showed 67 failures under a concurrent registry rewrite, split between
registry validation and a capsule-publication collision, none of which mention
this path. A count taken from a suite whose shared inputs are being rewritten
underneath it is not a measurement, so the claims that stand are the four
passing tests and the precise bite.

**A gap remains that decides whether this step helps at all.** Until a profile
receives an empty catalogue snapshot at creation, "filed but the snapshot write
failed" and "never filed" are indistinguishable, and the assessment refuses
identically for both. That is rowed separately, and it must not resolve the
ambiguity by treating absence as nothing-retained -- which is precisely the
revisit condition the new docstring names.
