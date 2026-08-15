---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:dcfeeb050c437b0dc11724df084520346c3085460c73ed37f91b6870879031cc'
step_id: 'S167'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh restore the hard-cutover absence gate's anti-tautology proof, whose fixture now trips the retired-name net as well as the package net so the two are no longer isolated and the proof asserts less than it reads as asserting, the gate's substantive absence assertions all passing while this one case is red at HEAD and was red before any current work touched it

## Scope

- `src/cadrumo/application/tests/test_custody_hard_cutover_absence.py`

## Description

- Trace the assertion and both nets with `git log -S` rather than reading the
  failure as a detector defect.
- Establish that neither net widened and no symbol was renamed: a tree-wide
  sweep rewrote the fixture's chosen symbol into the retired-name list.
- Re-found the fixture on a pinned surviving-substrate symbol and reach it in
  every import form the proof covers.
- Add the anchor that holds that symbol to the two properties the proof rests
  on, so the next sweep fails naming the symbol rather than a set difference.
- Correct two prose claims the same sweep falsified.
- Prove both nets bite separately, from outside the repository.

## Outcome

**Why the nets stopped being isolated.** Neither net changed. The proof was
isolated at birth: its dynamic-import case reached
`module.load_or_mint_bucket_dek()`, a surviving-substrate symbol the
provider-family name list does not contain, so only the module net could see
it. A later sweep commit deleted that symbol from the tree as part of a DEK-wrap
cleanup and rewrote its every textual occurrence to `get_master_key` --
including the occurrence inside this test's fixture SOURCE STRING, which is not
code the sweep was changing but text that happened to match. `get_master_key`
is a member of the retired-name list, so from that commit the package-net case
also tripped the name net and the assertion asserted strictly less than its
name claims. The same sweep rewrote the module docstring's list of what the
forwarding layer forwards, leaving it naming a symbol that layer does not
forward at all.

That is a fixture that lost its property, not a matcher that broke, and nothing
in a set-equality assertion said so -- which is why it surfaced as an opaque
detector mismatch and read as infrastructure noise.

**The repair.** The symbol the module-net proof reaches is now a pinned module
constant used by every form in the case, and a new anchor asserts the two
properties it is chosen for: it is still exported by the shared-master package's
facade, so the fixture describes a reach that can really exist; and it is not a
member of the retired-name list, so the module net is the only thing that can
see it. The facade's exports are read from source with the same AST walk the
rest of the module uses, rather than imported -- an application-layer unit test
should not pull the live persistence substrate in to answer a question about a
name. The chosen symbol is the active-bucket-session accessor, classified by the
preceding step as live per-profile session substrate rather than retired shared
master, so nothing here asserts that the surviving substrate is retired. The
ordered deletion of the genuinely retired surface remains blocked behind its own
open rows and was not touched.

**Both nets bite separately.** Proved by runtime rebinding from a script outside
the repository, so no tracked file was mutated:

- Module net broken (the shared-master package segment no longer names a package
  any fixture reaches): the package-net case reds, the name-net case stays green.
- Name net broken (the retired-name list emptied): the package-net case stays
  green, the name-net case reds.

The two are therefore independently provable again, and the gate can honestly
claim to test two things.

**The anchor bites too**, in both directions, so it is not decoration. Rebinding
the fixture symbol to a name that is both exported and retired reproduces exactly
the HEAD failure -- and the anchor now reds naming the symbol and the reason.
Rebinding it to a name the facade never exported leaves the package-net case
GREEN, because a module reach is still produced, while the anchor reds: that is a
fixture describing a reach that cannot exist, which the set-equality assertion
structurally cannot see. The anchor is strictly stronger than restoring the old
literal would have been.

**Two prose repairs from the same sweep.** The module docstring named
`get_master_key` among the forwarding layer's forwards; that layer forwards the
session accessor, the bucket-session open and resume, the serves-bucket
predicate, the session binding, the unsecured-bucket refusal and the login
throttle, and does not forward that symbol. The declaration entry for the
forwarding layer claimed a bucket DEK load-or-mint and a buffer zeroise reach;
the first names a symbol that no longer exists anywhere in the tree and the
second resolves to the per-profile custody package, not the shared-master one.
Both now describe the tree. The reason gate checks word count and destination
wording only, so it had been passing over false prose.

**Verified:** the whole gate at 12 passed, 0 failed, run with an explicit
`unit or integration` marker expression. Twelve, not eleven, because the anchor
is new; the eleven pre-existing assertions all still pass and the one that was
red at HEAD is green.

## Notes

- No assertion was loosened. The repaired case asserts the same equality against
  the same expected finding set; what changed is which symbol the fixture reaches
  and that the choice is now held to a stated property.
- The bite-proofs rebind module attributes at runtime from a scratchpad script
  and restore them, rather than editing a tracked file, because peer sessions are
  landing broad sweep commits against this worktree and would capture a
  tracked-file mutation. The final line of the proof re-runs every case with the
  originals restored and reports all green.
- The root cause is a general hazard rather than a one-off: a tree-wide textual
  rename cannot distinguish a fixture's source STRING from the code it is
  renaming, so any gate that hand-picks a symbol into a string fixture is one
  sweep away from silently losing the property that fixture exists to carry. The
  anchor added here is the local defence; the class is worth knowing about
  wherever else a proof embeds a symbol in a string.
