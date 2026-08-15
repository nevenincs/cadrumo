---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:0f6fdaaab35302fa475f7e73533bad84ef670d8a161d94fc999a0d9f7090c1ab'
step_id: 'S28'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh relocate the surviving per-profile session, wipe and identity residue into the custody package that the accepted decision names as sole authority, in one atomic move, so no surviving primitive is left behind a shared-master name

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/ and src/cadrumo/adapters/persistence/storage/custody/`

## Description

- Move the acceleration receipt, the wipe primitive and their tests into
  custody, narrowing their cross-package facade imports to intra-package ones.
- Rename the wipe primitive's error rather than carrying a shared-master name
  into custody, sweeping the error registry and all four locale catalogues.
- Promote the base64 codec to `core`, where both calling packages can reach it
  without importing each other.
- Land the whole move in one commit, with the regenerated API stubs.

## Outcome

The relocation landed as one commit of 32 files, with git recognising the
renames rather than a delete-plus-add pair, which is the shape the atomicity
rule asks for. The receipt was never shared-master material: it is a per-profile
artefact carrying a wrap of one profile's DEK, and its residence in the
shared-master package is what allowed one word to name two different custody
classes in this tree. Inside custody its imports narrow from cross-package
facade reaches to intra-package private ones, which the boundary rule permits
and prefers.

Both open rulings were taken the harder way, and both for the same reason. The
wipe primitive's error is renamed to name what it refuses rather than moved
under a shared-master name, because the primitive wipes any mutable buffer and
has nothing to do with the master key -- carrying the old name into custody
would have made the code assert something false about itself. The base64 codec
is promoted to `core` rather than duplicated, because its two callers sit in
packages that must not import each other, and a duplicated two-line wrapper
would have put one encoding decision in two places where only one would ever be
fixed.

Verified rather than assumed, in three independent ways. Tree-wide collection
reports 30122 tests collected at exit 0, so nothing anywhere imports a moved
symbol from its old home. A direct probe imports both packages and the promoted
codec, resolves the wipe primitive and the receipt lifecycle through the custody
facade, wipes a buffer and observes the refusal fire on an immutable one. The
affected suites run 358 passed with one failure, and that failure is the
Spanish-default-output test already attributed elsewhere and rowed separately --
it asserts English operator text with no language override in its conftest chain
and cannot pass on this tree in any state.

## Notes

This step also repaired a HEAD that could not import, which is why it was taken
by the team lead rather than left with its dispatched agent.

An earlier pathspec commit had taken this module from a working tree that
already carried these import rewrites. HEAD therefore referenced a core module
and a custody export that did not exist in it, and because the package facade
imports the receipt eagerly, the entire storage package failed at import from
any clean checkout. Nothing announced this: the committing agent's stat line
read exactly the one file it intended, because the file count was right and only
the content was wrong. Landing the remainder of the atomic change is the repair,
and it is the same lesson the campaign has now met from both sides -- an atomic
change is only atomic until someone commits half of it.

Two surfaces had to be rebuilt from HEAD rather than taken from the working
tree, because peers were mid-change in the same files. The four locale
catalogues carried a peer's OSS/IOSS invoice keys alongside this rename, and the
core API stub index carried a peer's record-design-epoch module alongside the
promoted codec. Both were reconstructed as HEAD content plus only this change,
verified by diffing each rebuilt blob against HEAD and confirming the rename was
the sole difference. Taking either file wholesale would have committed work
belonging to someone else; taking neither would have left the error registry
pointing at a message key present in no catalogue.

The dispatched agent's question about whether moving the wipe primitive unblocks
the wipeable-key-material work is answered in the affirmative and by execution
rather than by reading: custody now imports and calls the primitive directly
through its own package, proven live, with the import cycle that previously
blocked it gone.
