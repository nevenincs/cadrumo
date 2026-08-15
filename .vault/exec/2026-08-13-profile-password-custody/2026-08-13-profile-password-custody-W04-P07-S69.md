---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:7951e405b050500030006924bf51fc85123bc02c596154eda6c467c6a9c132e8'
step_id: 'S69'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh remove the second bucket-root creator that survives as dead production code

## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_layout.py`

## Description

- Establish the helper's real reach and whether publication can replace it.
- Remove it from the production package without stranding its exports.
- Land the relocation and its consumer sweep as one commit.

## Outcome

The second bucket-root creator is gone from the production package and from the
shipped artefact. The helper is relocated into the test-support package, which
the distribution configuration excludes from the wheel -- so it leaves both the
import surface and the built package, which straight deletion plus migration
would not have achieved for the production side. One creator of a bucket root
remains: publication.

**The row's stated case was weaker than the truth.** It described a helper that
could be wired back up to reproduce a similar defect. Measured, the helper creates
the EXACT path publication's atomic no-replace rename must claim -- the capsule
commit lives inside the bucket directory, so the two resolve to the same
location. A wired-up helper would not invite a comparable defect; it would
reproduce the capsule-publication collision this campaign already fixed, in the
same place.

**The proposed remedy did not apply, and the reason matters.** The dispatcher
suggested publishing a capsule instead of keeping the helper. Publication and the
helper produce DIFFERENT artefacts: publication renames a staged capsule into
place and writes the commit marker, and does not create the database and blob
children. The tests calling the helper are about manifest input-output,
lockfiles, layout and a language hint -- they need that tree and never publish.
So this was never a case of tests failing to reach the seeding surface; the
seeding surface does not produce what those tests are about.

The path-length error was promoted to the owning facade FIRST, because the
relocated helper raises it from outside the package -- promotion as a
precondition of the consuming change rather than a follow-up.

Verified independently: zero residual production references, the facade no longer
exports it, and the densest consumer suite is 164 passed.

## Notes

A proposed test move was recommended AGAINST by the implementer and the reasoning
was accepted. The layout test module is not a file that happens to contain
provisioning tests -- its docstring is a worked oracle argument for why the
provisioning assertions and the path assertions must sit together, with bare
literals as the independent oracle, because expressing the expected side through
the accessor would assert the accessor equals itself and defend nothing. Three
further tests in it concern production artefacts and share the same pinned
literals. Splitting would have fragmented the one file documenting why its halves
belong together. Left in place, importing from the new home, and reversible if
ever wanted.

Behaviour was proven by direct probe rather than assumed: the relocated function
still creates the child tree, returns a record equal to the path resolver, stays
fail-closed on re-provision, and still refuses an empty identifier.

A measurement hazard surfaced that the campaign had not recorded. Wider suites
were unquotable because a peer was rewriting the registry tree concurrently,
producing a load error that names its own condition -- registry directory changed
during cache fingerprinting. This is cross-PROCESS contention, which sequential
running does NOT protect against, unlike the parallel collection race the local
execution rule describes. The implementer declined to quote any count from those
suites and rested the evidence on the direct probe and the one suite that was
unaffected.

One self-reported error is on record: a lint autofix was run package-wide rather
than scoped, applying thirteen fixes tree-wide. It was deliberately NOT reverted,
because the touched set includes peers' substantial in-flight work and a blind
revert would destroy real edits to undo a lint fix. None are in this commit's
pathspec.
