---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
step_id: 'S126'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium enrol the custody capsule formats in the governed persisted-format inventory

## Scope

- `src/cadrumo/core/compatibility_lifecycle.py and src/cadrumo/adapters/persistence/storage/custody/`

## Description

- Enrol the three capsule file formats, arguing a durability class for each
  rather than inheriting one from its neighbours.
- State why the capsule's directory categories are deliberately excluded.
- Correct the gate defect the enrolment exposed.

## Outcome

All three capsule formats are enrolled as DURABLE, each with its class argued
from what is lost when it stops being readable rather than assigned by
proximity.

The password envelope: unreadable means no password unwraps the bucket's data
key ever again, and every encrypted record under it is lost. This is the
obligation the retired keystore entry used to carry, now under different
custody.

The commit record: the sole discovery proof for a capsule. Recognition reads
this marker and nothing else, and returns "no such profile" when it will not
parse. There is no rebuild path and its self-digest cannot be reconstructed by
hand, so losing readability does not corrupt the profile -- it makes the profile
cease to exist while its bytes sit on disk.

The recovery envelope, where the argument is sharpest: **optional to CREATE is
not the same as discardable once created.** The application cannot re-derive
recovery material the way it rebuilds a session or a throttle, and its
readability is load-bearing exactly in the case it exists for -- a forgotten
password -- where failing to read it turns a recoverable profile into total
loss. That reasoning is what separates DURABLE from REGENERABLE, and reading it
off the neighbours would have got it wrong.

The capsule's custody and data CATEGORIES are deliberately excluded, with the
reason stated: both are directories rather than file formats, so they carry no
bytes to keep readable, and what they contain is enrolled under its own keys.

## Notes

The gap this closed is the one worth remembering. The three formats were absent
from the inventory while the retired plaintext manifest was present in it --
**the artefact being removed was governed and the artefact replacing it was
not** -- and the inventory's blindness is why. Nothing enumerates the tree
against the inventory, only floors against it, so a format that never appears
there never fails anything. The comment claiming a new format "fails the gate
rather than passing by omission" was false in both directions, and being false
inside a governing constant is the most consequential form of that defect: it
sits where a reader is least likely to doubt it.

**A finding first reported here was wrong and is retracted.** The step initially
reported that the gate test repeated the very staleness its own docstring
records fixing -- hand-listed expectations sitting beside a derived reference
set. That reading was the opposite of the truth, and the retraction matters more
than the enrolment.

The two are different tests doing different jobs. The reference set IS derived,
correctly, because a hand-listed mirror of it once went stale. The parametrised
expectations are hand-listed **on purpose**: they are the anti-tautology arm, and
deriving them from the inventory would compute the answer the same way the
function under test computes it, so every case would pass by construction. Going
stale when the inventory changes is the PRICE of an independent expectation, not
a defect in it.

The reason is now written into the parametrisation itself, so the next reader who
finds it stale does not "fix" it by deriving -- which would silently convert a
real gate into a tautology. That is a sharper hazard than the one first reported,
and it exists only because the correct construct and the defective one look
identical: a hand-list beside a docstring about a stale hand-list reads as the
same mistake when it is the opposite.

The general form is worth more than the instance. **A construct that resembles a
known defect may be the deliberate defence against it**, and the campaign's own
habit of pattern-matching against recorded failures is what makes that misread
likely rather than unlikely.
