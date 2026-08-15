---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:dc57a803f12b1f3d0e719b4ff9483d816622daf25fc68fdea435399db3c52d4a'
step_id: 'S113'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh carry the login-gating principle recovered from a deleted allowlist comment into the archive export restore work, that a verb whose output leaves the encrypted store must stay login-gated because a target-scoped unlock does not establish recency, the principle having been justified by a cited test that does not exist and now being recorded nowhere else

## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`
- `src/cadrumo/entrypoints/cli/tests/test_login_gated_verbs_never_exempt.py`

## Description

- Recover the principle and its full grounds from the deleted comment in history.
- Record it as a typed refusal registry beside the exemption list it constrains.
- Enforce it with four gates: never exempt, never swallowed by a prefix, anchored
  to a declared family, and never stated without grounds.
- Prove each gate bites by granting the refused verb an exemption from outside
  the repository.

## Outcome

The principle, stated as it must survive: a verb whose OUTPUT leaves the
encrypted store must stay login-gated, because a target-scoped unlock does not
establish recency. The login gate demands a session whose idle and absolute
deadlines have not elapsed. A verb that names its own target and unlocks that
bucket itself satisfies every mechanical test the target-scoped exemptions are
admitted on, and still establishes nothing about how recently the operator
authenticated. What distinguishes these verbs is their OUTPUT, not their
plumbing.

It now lives as data rather than prose, in a refusal registry beside the
exemption list it constrains, with the grounds carried per entry. The choice of
home is the row's own argument: a principle carried only in a comment was
justified by a citation that outlived what it cited, and was then deleted with
the block it sat in. A docstring on the gate it governs would have failed the
same way, and there is currently no gate to hang it on, because the verb it
governs does not exist in the tree at all right now.

Two verb paths are enrolled: the archive export and the profile export. Both are
the paths the operator-surface contract's profile family anticipates. Neither
resolves today, which is the point of binding the refusal to the path rather
than to a live command: the refusal is in force the moment the verb lands, not
filed afterwards.

Four properties are enforced. The refused path is never bootstrap-exempt. No
exempt entry is a PREFIX of a refused path, which the leaf check alone would
miss, since exempting the profile group would carry the export verb with it.
Each refusal hangs off a family the operator-surface contract declares, so a
family rename reds rather than silently retiring the refusal. And each refusal
states grounds substantial enough to survive a re-derivation pass, because a
bare refusal is the shape a later cleanup deletes as noise.

The family anchor is as deep as the tripwire can go, and this was re-derived
against HEAD rather than assumed. A command family deliberately declares no
command inventory: which verbs it contains is established solely by the live
command tree. So a refusal naming a verb not yet built cannot be anchored at the
leaf. A rename of the leaf itself therefore remains the hand sweep every verb
rename in this tree already owes the exemption list, and the record says so
rather than implying coverage it does not have.

All four gates were proven to bite, by rebuilding the tables in memory from
outside the repository: granting the refused path an exemption reds; exempting
the profile group so the prefix swallows it reds; hanging a refusal off an
undeclared family reds; and a refusal with token grounds reds.

Correcting the row's own framing against the tree: the cited test was not one
that never existed. It was written on 2026-08-03 in the same commit that added
the comment, asserting the exception and its grounds while confirming the
sibling exemptions still held. It was lost in a later worktree consolidation,
and the comment was deleted afterwards with the surrounding block. The
distinction matters for what the fix has to be. A fabricated citation is an
authoring failure; a citation outliving what it cited is a structural one, and
it is now caught by the cited-test gate recorded under S118.

Verification: 65 passed across the two gate modules, lint and the canonical type
checker clean.

## Handover to the restore and export rows

The principle applies directly to the open password-only restore and
artifact export or import row, and to the row exposing the restore,
restore-recover and delete verbs. Neither is executed here. What those rows must
carry, verbatim:

A verb whose output leaves the encrypted store must stay login-gated, because a
target-scoped unlock does not establish recency. The login gate demands a session
whose idle and absolute deadlines have not elapsed; a verb that names its own
target and unlocks that bucket itself never establishes that. Restore and import
bring data in and are not governed by this. Export, archive export and any
recovery-artifact emission are governed by it, and must not be added to the
bootstrap-exempt allowlist however cleanly they qualify on the target-scoped
reading. If either row names the export verb something other than the two
enrolled paths, the refusal registry entry must be renamed in the same change:
the family anchor catches a family rename, not a leaf rename.

The enforcement is already in place, so the failure mode for those rows is a red
gate rather than a silent widening, provided the verb keeps one of the enrolled
names.

## Notes

The refusal registry is enforced but the enrolled paths are inert until the verbs
exist. That is deliberate and is not the armed shape the exemption list suffers
from: an entry that only ever FORBIDS cannot grant anything, so a stale refusal
costs nothing, while a stale exemption grants an unreviewed one.

A peer's broad commit swept these files into the repository while the work was in
progress, so the changes are at HEAD rather than in the working tree. Nothing was
committed from this seat.
