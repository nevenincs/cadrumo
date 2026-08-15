---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:245af293c4ff24d075bb1a887a311441ce3c9c75ddf42fbc6dc815387dfe2f27'
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

Verified in three ways, and the verification was still incomplete. Tree-wide
collection reports 30122 tests collected at exit 0. A direct probe imports both
packages and the promoted codec, resolves the wipe primitive and the receipt
lifecycle through the custody facade, wipes a buffer and observes the refusal
fire on an immutable one. The affected suites run 358 passed with one failure,
and that failure is the Spanish-default-output test already attributed elsewhere
and rowed separately -- it asserts English operator text with no language
override in its conftest chain and cannot pass on this tree in any state.

What all three missed is recorded below, because the gap is the more useful
finding.

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

The relocation shipped incomplete and the follow-up commit is part of this step.
One consumer reached eight of the moved names as ATTRIBUTES of the old module
rather than importing them, and every one of those call sites raised at HEAD.

That class is invisible to everything this step used to verify itself. An
attribute reach resolves at CALL time, so there is no import statement for
collection to fail on -- the tree-wide collect stayed green at exit 0 both
before and after the break. A grep for imports of the moved names finds nothing
either, because the consumer imports only the package. The suites that would
have caught it were outside the scope run. So a clean collection does not clear
a relocation, and the earlier claim that this move was verified three
independent ways was true about three things and silent about the one that
mattered.

The reaches were recovered because the agent that authored the relocation named
them explicitly in its report, having swept them itself before it was cut off;
they were then confirmed against HEAD directly rather than accepted on the
report. A sweep afterwards confirms no attribute or dynamic reach of any moved
name remains anywhere in the tree.

The standing question about whether moving the wipe primitive unblocks the
wipeable-key-material work is answered in the affirmative, by execution rather
than by reading, on three measurements. Custody's import sites reaching the
shared-master package number zero, so the cycle that blocked it is gone and
custody needs no import of that package at all. A custody-internal wipe runs
end to end: thirty-two non-zero bytes in, thirty-two zero bytes out, through
custody's own package. And a custody module already consumes the primitive as a
sibling import, which is precisely the shape recovery and password unwrap need
-- demonstrated live rather than predicted, so the next step inherits a proven
capability instead of a hypothesis.

The consumer suites afterwards run 321 passed with seven failures, none of them
reachable from this change: every one is a registry validation error belonging
to another campaign's in-flight legal-catalogue and export-layout work. The
attribution that matters is the absence rather than the count -- zero
`AttributeError` anywhere in the run, which is the signal that the repointed
call sites resolve.

One reference was deliberately left untouched. The preimage ledger under the
quality tooling names the old error code, but it is extracted from an immutable
source commit and validated against that history, so editing it would falsify a
historical record rather than update a stale reference.
