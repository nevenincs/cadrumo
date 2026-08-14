---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:2438082e887f4a8832b507a74fe9036b957c68fa02db0fae889b675dd953e9ec'
step_id: 'S40'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium confirm or refute that the modelo export stages fichero bytes through a predictable unhardened temporary name at an operator-chosen destination, and if confirmed bring that staging under the hardened write contract that governs sensitive financial data

## Scope

- `src/cadrumo/application/modelo/_export.py`

## Description

- Establish by reading the current export path whether the staging name is
  predictable and unhardened, before proposing any change.
- Delegate the staging to the canonical hardened write primitive rather than
  hardening a second write path inside the export module.
- Prove the property at the primitive, and ratchet it in the source tree so a
  future predictable staging name cannot reappear unnoticed.

## Outcome

Confirmed, and closed. The export staged fichero bytes through a predictable
temporary name at a destination the operator chooses, which is both a
pre-creation and symlink surface and a plaintext residue risk for filing-grade
data. The repair moves the guarantee down a layer: the export now stages through
the hardened write contract in `src/cadrumo/core/atomic_write.py`, which is the
single-writer primitive that already owns atomicity, rather than growing a
second hardened path beside it.

The regression deliberately does NOT depend on the profile-capsule seeding
fixture, which is red for an unrelated publication collision. It sits at the
write primitive itself against a real filesystem, plus a source-tree assertion
that needs no fixture at all. That was the right call: the alternative would
have been rebuilding capsule seeding in order to avoid capsule seeding, which
would have created exactly the second seeding path this campaign exists to
remove.

Verified independently rather than accepted from the report: 44 passed across
the write-primitive and staging-name suites, sequential.

## Notes

Provenance correction, recorded because it becomes unrecoverable once memory of
the day fades. The source-tree ratchet `src/cadrumo/tests/test_staging_name_unpredictability.py`
belongs to this step, but it is not in this step's commit: a first commit
attempt blocked on a held index lock had already staged the new file, and a
concurrent bare commit from another campaign consumed it. The content is
byte-identical to what this step authored, so nothing is lost, but the file's
recorded history attributes it elsewhere.

The generalisable lesson is that staging an untracked file is not free in a
shared tree: `git add` seeds a shared index that any concurrent bare commit will
consume. The three files that were never staged rode a pathspec commit safely.

One count in the original report was quoted from a parallel run and later
withdrawn by its author, who re-measured sequentially. This repository's default
test invocation is parallel, so every figure taken from it is unreliable until
re-run sequentially -- a correction that applied equally to a figure recorded
elsewhere in this campaign.
