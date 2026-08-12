---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:5c8b17f98ccd5ec248988d9cd0ff2a58290538a10e8c8c48aec558fcd943f193'
step_id: 'S39'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Delegate the export provenance manifest writer to the new core publish-once tier and delete its hand-rolled staging sequence, because the earlier decision to document that writer as a deliberate superset rested on an untested claim that this working tree cannot support os.link, and measurement shows os.link both links and refuses an existing target atomically, so the compromise that justified leaving a parallel write path in the tree never existed and the architecture boundary forbids re-implementing a write path rather than delegating to the single-writer primitive, noting the delegation must also strip the now-false unavailable-on-this-platform paragraph from the writer docstring and that the existing refusal test should keep passing unchanged since the contract is preserved and only its implementation moves

## Scope

- `dev/registry/_provenance_manifest.py`
- `dev/registry/tests/test_export_tree.py`

## Description

- Check the row against HEAD before starting it, per the standing rule that a
  peer may already have landed a step, and find it fully landed.
- Verify the delegation is real rather than nominal: the writer calls the core
  publish-once tier, the hand-rolled staging sequence is gone, and the
  now-false unavailable-on-this-platform paragraph has been replaced by a
  paragraph stating why the earlier claim was wrong.
- Verify the refusal contract survived as a translation rather than a
  re-implementation, and that the pinned refusal test passes unchanged.
- Re-run the row's named gates at current HEAD rather than trusting the
  landing commit's own run.

## Outcome

Already landed as `ccdf12eb0947a5bd9a986728787482adb78ed95b` (30/39 in the
writer, 10/9 in the export-tree gate), on the core publish-once tier added by
`eecd719820`. Net effect in the writer is a deletion, which is the correct
shape for a delegation.

Re-verified at HEAD rather than accepted from the commit message. The
export-tree gate is 26 passed; the publish-once tier's own tests are 2 passed.
The writer's refusal is preserved by catching `FileExistsError` from the tier
and raising the same registry error with the same message, so the contract the
pinned test asserts is unchanged while its implementation moved.

The parent-directory precondition was deliberately NOT delegated and the
docstring now says why: a missing parent means the export tree was never
built, which is a registry error, and the core tier would create the directory
and mask it. That is a real distinction rather than residue, and leaving it
in place is what keeps this a delegation rather than a blind adoption.

This row exists because S38 ruled the opposite way and that ruling has to stay
legible. S38 recorded the writer as a deliberate superset of the hardened
tier on two grounds: that no core tier refused a pre-existing target, and that
a genuinely atomic publish-once needed `os.link`, which this project's
network-share working tree could not reliably provide. The second was asserted
and never measured, and measurement showed it false. With it the first ground
falls as well, because a core tier built on that primitive then becomes
available. What stood was not a superset but a parallel write path, which the
architecture boundary forbids.

## Notes

Closed on inherited evidence, and the record says so plainly rather than
implying this session performed the work. The step's verification is a
re-run of its named gates at current HEAD, which is the strongest claim
available for a landing this session did not make and is the standing remedy
for a step whose commit predates its record.

The durable lesson is one this campaign has now recorded twice: a
justification resting on an unmeasured platform claim is a decision waiting to
be reversed, and the reversal is cheap only because S38 wrote its two grounds
down explicitly instead of concluding "deliberate, do not touch". A note that
states its premises can be refuted by measurement; one that states only its
conclusion cannot, and would have preserved the parallel write path
indefinitely.
