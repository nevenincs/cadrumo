---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:54cec62b5b25cba39f3bdc732fd0514f5bd9e3615ca5ff0b5c22be05808b77c9'
step_id: 'S29'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh extend the existence-only retired-path detector to recognise retired keystore members alongside the plaintext manifest, so a retired shared-master store is detected and routed to re-enrolment rather than read

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/_capsule_discovery.py`

## Description

- Add a second closed retired-member inventory naming the shared-master-wrapped bucket
  data-encryption key sidecar, beside the existing plaintext-manifest inventory.
- Generalise the two platform scanners over the root and the member tuple they walk, so one
  anchored, no-open implementation serves both stores instead of a copy per store.
- Take the keystore root explicitly on the detector and the refusal, because it is a sibling of
  the buckets root rather than anything nested beneath it.
- Name the keystore root in the refusal context alongside the buckets root, so the destructive
  reset the refusal prescribes covers every location that carries the detected material.
- Move the refusal ahead of the empty-buckets-tree shortcut at the sole production caller, since a
  store can carry retired key material with no buckets tree at all.
- Prove the detector bites in both directions.

## Outcome

**What is now recognised.**

The detector previously walked one root, the buckets root, checking each candidate directory for
one retired member: the plaintext `manifest.toml` that was the former profile authority. It now
also walks the keystore root, checking each candidate directory for `bucket.dek.json`, the
shared-master-wrapped bucket data-encryption key.

That name is the right target, and the search for it was the substantive part of this row. The
keystore is enforced to be a SIBLING of the buckets root, never nested inside a bucket, so nothing
the previous detector walked could ever reach it. A store could therefore present an entirely
current-format buckets tree while still holding key material whose only route is the retired
shared-master schedule, and the previous detector reported that store as clean and profile-less.
The wrapped-DEK sidecar's production writer was deleted earlier in this campaign, so no
current-format store can create one; its presence is unambiguous evidence of a retired store.

The shared-master `secrets/` members are deliberately NOT enrolled. Their store directory is
operator-overridable and not derivable from the storage root the detector is handed, and more
importantly the file-backed provider that writes them is still live pending two open rows, so
enrolling them would refuse stores that currently work. A detector that refuses everything is
worth nothing, and that is the shape it would have taken.

**What it still refuses to do.**

Existence-only is unchanged and was treated as the invariant, not as an implementation detail. The
new arm stats a name and stops. It opens nothing, reads nothing, parses nothing, digests nothing,
and infers no identity from what it finds. Nothing about the retired wrapped DEK is adopted,
migrated, or carried forward; the outcome is the same stable refusal with destructive-reset and
re-enrolment guidance the manifest arm already produced. That is the point of the row: routed to
re-enrolment rather than read.

**The refusal stays instructive, and its scope is unchanged.**

The context now names both scanned roots rather than one. That is required for the guidance to be
actionable: the prescribed remedy is a destructive reset of the store, retired key material lives
outside the buckets tree, and naming only the buckets root would send an operator to clear a
directory whose removal leaves the refusal standing. Each value names a directory, never a bucket
and never an identity, so the refusal still discloses nothing the detector declined to infer.

The refusal's scope was not touched. It remains whole-store rather than per-profile, which is the
subject of a separate open row that this executor does not own. Only what is recognised changed.

No new operator-facing message was introduced, so no locale key is needed. The refusal travels
through the existing typed refusal carrying its stable reason and its closed recovery-guidance
pair, and the command-line surface already renders it; no bespoke advisory field was added
anywhere.

One behavioural change at the sole production caller is worth stating explicitly. The refusal now
runs before the shortcut that returns an empty profile set when the buckets tree is absent. Without
that reordering the newly recognised case would still have been missed, because the store this arm
exists to catch is exactly the one whose buckets tree may be gone while its keystore is not. The
cost is two existence checks on a path that already performed one.

**Proof that it bites, in both directions.**

Both proofs are runtime mutations applied from outside the repository, so nothing under the source
tree changed and a crashed run could leave no residue a peer sweep might commit.

Detection direction: with the retired-keystore inventory emptied in memory, the new keystore test
fails, reporting an empty result where the wrapped-DEK sidecar was expected. The clean-store test
stays green throughout, confirming the failure is the detection arm and not collateral.

Over-refusal direction: with the inventory widened to also name a LIVE keystore sidecar, the
clean-store test fails, reporting that sidecar as retired on a store that is entirely current. The
keystore test stays green. This is the half that matters most, because it is the failure mode a
detector extension invites, and it is now pinned rather than assumed.

The clean-store case exercises a genuinely published capsule whose keystore carries the live
persisted-session record and the live login-throttle cache, and asserts discovery still returns
that capsule. The retired case materialises a real sidecar with real bytes and asserts, through an
audit hook on the interpreter's open event, that those bytes are never opened.

**Verification.**

The custody suite passes in full, including the import-graph gate that forbids the derivation child
from reaching the shared-master package; this row added no import to the custody package at all.
The custody and master-key suites, the capsule-lifecycle and active-profile-resolution suites, and
the hard-cutover absence gate ran together: 320 passed, one failed. That one failure is the
pre-declared, already-red detector-vocabulary test tracked by a separate row, whose assertion
concerns an unrelated symbol name set.

The wider storage suite reports 39 failures, none attributable here. Every failing module was
checked against the symbols this row touched and none references the detector, the refusal, or the
discovery entry point. This rests on attribution rather than on a clean run at the pre-change
baseline, and that distinction is stated rather than glossed.

The linter, the formatter and the type checker are clean on every changed module.

## Notes

The signature of the detector and of the refusal both changed, taking the keystore root as a
required keyword argument. Making it optional was considered and rejected: a detector that silently
skips half its inventory depending on how it was called is a worse failure than a compile-time
break, and there is exactly one production caller plus one test module to update.

The buckets-root arm still names its retired member with a literal rather than reading the storage
taxonomy, which already declares the same name and marks it retired. That duplication predates this
row and the new arm matches the established local shape rather than diverging from it; unifying both
against the taxonomy is a reasonable follow-up but was not in this row's remit.

Peer commits landed over this worktree mid-run and absorbed these changes into their own sweeps.
Nothing was committed from here.
