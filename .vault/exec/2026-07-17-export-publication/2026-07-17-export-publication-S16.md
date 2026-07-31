---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:ea1132b2846b569b51f9c5cc2135fd931b4f4ecd7f8b7c7faea79170a38017cb'
step_id: 'S16'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Close the pre-journal crash window so no cleartext bundle can exist on disk without a journal entry naming it, recording the durable operation before staging rather than after, and extending orphan removal to the hardened writer's own inner temporary file whose name the current suffix guard rejects, gated on a hard-killed child crashing inside the widened window with no cleartext surviving

## Scope

- `src/cadrumo/application/user_profile/_bundle_export.py`
- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`

## Description

- Reproduce the reviewer's finding: staging ran before the journal, with category
  derivation, model construction, and a journal write that can wait on the repository
  lock all sitting between the cleartext landing and the record naming it.
- Derive the staged path without touching disk so the journal can name the file it is
  about to create.
- Write the durable operation record before staging, and stage only after it lands.
- Discard a journalled operation whose staging then failed, best-effort, leaving
  anything unclearable journalled for the next sweep.
- Extend orphan removal to the hardened writer's own inner temporary sibling, which
  holds the full bundle and does not end in the staged suffix.
- Match those inner temps over a directory listing rather than a glob, so a literal
  bracket in an operator-chosen destination cannot be read as a character class.
- Add a control proving the crash harness genuinely reaches staging when unblocked.
- Add the kill proof: hold the journal repository lock, hard-kill a child inside the
  widened window, assert no cleartext and no journal survive.
- Add a proof that reconciliation clears a reproduced hardened-writer inner temp.
- Expose the repository's lock target so the crash proof needs no private reach.

## Outcome

No cleartext bundle can now exist on disk without a durable record naming it. That is
the whole crash contract, because recovery is journal-driven: bytes staged without a
journal entry pointing at them were unreachable by every surface, including the
maintenance verb added for exactly this class of leftover.

The ordering is safe in the other direction too. A crash between the journal write and
a completed staging leaves a prepared operation whose destination lacks the recorded
digest, so reconciliation clears the path it names whether that file exists, is
half-written, or was never created, and emits no event for something never published.

Deriving the disclosure categories before staging is a second gain that fell out of the
reordering: an unclassified schema field now refuses before any cleartext is written
rather than after.

The compounding half mattered as much as the window. The hardened writer stages through
an inner sibling and unlinks it in a finally that a hard kill never runs; that file
holds the whole bundle and does not carry the staged suffix, so the orphan guard
rejected it and the existing assertions could not see it. Recovery now enumerates those
temps from the same prefix, and the test helper deliberately matches the suffix
anywhere in the name rather than at the end, so the assertions are no longer blind in
the same way the guard was.

Non-tautology is observed. Restoring staging-before-journal leaves cleartext after the
hard-killed child; restoring the narrow guard leaves the reproduced inner temp. Both
proofs go red on exactly those artefacts.

## Notes

The kill proof pairs with an explicit non-vacuity control, because a kill test that
finds no cleartext proves nothing on its own -- the child might never have reached
staging. The control runs the same harness unblocked and asserts it does journal and
stage.

The inner-temp proof reproduces the on-disk state a hard kill leaves rather than racing
a real kill inside the writer. The file is real, its contents are the real bundle, and
the production removal path runs; only the moment of creation is arranged.
