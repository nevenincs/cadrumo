---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:5f40461970bad8fc9e2c5b0d9ed1a99aa412ec43d0c808916b765ec76a25a920'
step_id: 'S33'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Repair the two pre-existing authority cache invalidation fixtures that die during construction because they declare a legal review status whose vocabulary has since been tightened, restoring real coverage of the fingerprint-backed process cache and the fragmented-revision invalidation property these tests are named for and which went unproven while the staleness defect sat undetected

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Move the shared minimal legal-catalogue fixture in `test_authority.py` from
  the retired `reviewed` token to the fail-closed `pending_review`, and drop the
  `reviewed_at` and `reviewed_by` fields, which a pending entry may not declare.
- Leave both source-reference `review_status` fields untouched: that field is a
  different type whose vocabulary still admits exactly `reviewed`, so changing
  them would have broken working rows.
- Rewrite the fragmented-revision invalidation test so its mutation lands in a
  fragment file below the revision directory rather than in the scalar manifest,
  appending a second casilla to the casillas fragment.
- Assert the scalar `revision.toml` is byte-identical across that mutation, so
  the fragment-only claim is checked in the test rather than assumed by a reader.
- Assert on the loaded casilla ids either side of the reload, so the second
  authority is proven to carry fragment content the first did not.
- Clear the fingerprint cache before the first load, matching the sibling
  invalidation tests, and delete the redundant function-local re-import of the
  clear helper that the module already imports.

## Outcome

Both named tests reach and exercise their assertions. The file moves from eight
failed and two passed to three failed and seven passed. No test was added or
removed, and nothing imports this module, so the file delta is the whole delta.

A sequential run of the whole registry test directory afterwards finished at 602
failed, 3789 passed, 122 errors in 38 minutes, and the directory-wide result
confirms the file-level measurement in situ: exactly three failures come from
this module, all three the packaged-corpus filing-grade class, and every test
this Step restored passes there too. That absolute figure must NOT be differenced
against the previous directory run recorded in this campaign. Peers landed
commits between the two, and the later run collected five more tests than the
earlier one, so the difference between them measures the shared tree's churn
rather than this change. The same-HEAD file measurement above is the delta.

The vocabulary repair was narrower than the row's description implied. Three
`review_status` literals sit in that fixture, but only the legal-catalogue one is
invalid: the source-reference field is typed as a literal that still admits only
`reviewed`, so two of the three had to stay exactly as they were. Repairing the
one shared legal entry also restored three further tests in the same file that
died on the same fixture -- a reused-number rejection test, a legacy-marker
revalidation test, and a source-evidence invalidation test -- which were not
named in the row but could not be left broken by a fixture this Step had to edit
anyway.

The larger finding is that the vocabulary tightening was not the only thing wrong
with the fragmented-revision test. Its mutation rewrote the whole revision, and
the only content that actually differed between the two renderings was the scalar
`source_refs` value, which the fragmented writer places in `revision.toml` -- not
in a fragment. The test named for recursive fragment fingerprints was therefore
mutating the manifest, and a fingerprint walk that never descended into the
fragment subdirectories would have passed it. Fixing only the vocabulary would
have restored a green test that did not prove its own name, which is the outcome
this row explicitly warns against. The mutation now appends a casilla to the
casillas fragment while the manifest stays byte-identical.

Each assertion was proven to bite by breaking the behaviour at runtime from
outside the repository, through pytest plugins on the path; no tracked file was
mutated for any proof.

Freezing the tree fingerprint to a constant reds both tests on their invalidation
assertions. Making the fingerprint blind to everything below a revision directory
except the manifest reds the fragmented test alone and leaves the process-cache
test passing, because that test's mutation still reaches the manifest. That
asymmetry is the evidence the fragmented test now earns its name -- and, by the
same observation, the evidence that its pre-repair mutation would not have, since
that mutation was identical to the one the surviving test performs. Making the
fingerprint novel on every call reds the process-cache test on its cache-hit
assertion, covering the opposite defect.

## Notes

This Step consumes no entry from the Deletion inventory. Nothing was deleted
beyond one redundant function-local import statement.

Three tests in the same file remain red and are deliberately not repaired here.
They resolve filing-grade snapshots against the real bundled corpus, where no
revision carries an operator review stamp, so they fail on the filing-grade
refusal rather than on fixture construction. The only thing that would make them
pass is a written operator review attestation, which no program or agent may
produce; they belong to the campaign's grade work, not to a fixture repair.

Worth recording for whoever revisits the cache: another layer's test file
explicitly delegates its coverage to the process-cache test repaired here,
stating that it does not re-prove tree-change re-derivation because the owning
layer already does. That delegation was live for the whole period this test was
dying during construction, so the absence of coverage was wider than one file.
The delegation's wording remains accurate after this repair.

The repaired tests keep their explicit fingerprint-cache clears rather than
relying on a mutable authoring tree recomputing its fingerprint on every call.
The clears make the tests independent of the caching policy, so a later change to
the mutability or expiry rules cannot quietly turn either test vacuous.
