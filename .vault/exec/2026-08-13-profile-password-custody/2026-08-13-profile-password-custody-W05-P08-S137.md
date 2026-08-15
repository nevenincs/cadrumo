---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
step_id: 'S137'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh restore the retention detail to the hold projection so the deletion preflight can answer a count and a floor and a safe-erase date rather than two booleans

## Scope

- `src/cadrumo/application/filing/_profile_filing_retention.py and src/cadrumo/application/user_profile/`

## Description

- Expose the retention position the authority already computes, instead of
  discarding it at the projection boundary.
- Make the defaulted-zero case structurally impossible rather than merely
  avoided.
- Produce the coverage checklist the retirement half needs.

## Outcome

**A pure narrowing-undo, exactly as scoped, and not the larger case the row
allowed for.** The filing authority already computed the whole retention
assessment — per profile, already aggregated — and then discarded everything but
a single boolean on the return line. So no aggregation was missing and no second
retention path was created: the full answer and the flag now come from one call,
which adds a view rather than a parallel computation.

**The fail-open caution is enforced structurally rather than remembered.** There
is no empty-assessment fallback anywhere; an absent or unreadable snapshot
raises. The snapshot load, identity check and byte check are hoisted into one
helper, so the flag and the detail cannot come from differently validated
inputs. That closes the shape of the earlier defect — a decision that blocks
nothing and reports zero retained records — by construction rather than by
vigilance.

Bite-proved in both directions from outside the repository: forcing the floor to
report nothing retained fails the two detail tests and correctly leaves the
absence test untouched, while degrading absence to an empty assessment fails the
absence test alone. Verified independently at three passing on the new module,
with no empty-assessment fallback present in the source.

## Notes

**The deferral that started this whole investigation is obsolete, and that is the
third instance of the same trap.** The producer's docstring said retention
"requires decrypting the exact profile record under an authenticated session",
which is why the populated assessment was believed impossible to produce. The
filing owner persists a plaintext snapshot and assesses from that, needing no
session at all. So the stated constraint has not been true for some time, and it
was read as a fact about the present.

That is now three: a deferral naming a future that had already arrived, a
comment describing a source of truth that had moved, and here a constraint that
had been lifted. **A docstring is a claim about the moment it was written**, and
this campaign has been punished for reading one as current three separate times.

The step also produced the coverage checklist the retirement half needs, as a
list rather than as the memory of an investigation. Every field of the older
contract now has a named live source except one: the manifest digest, whose
subject retired with the plaintext manifest. That single open item is ruled
separately — the field has no production producer anywhere and its only
constructions are hand-built fixtures — which leaves the retirement unblocked.
