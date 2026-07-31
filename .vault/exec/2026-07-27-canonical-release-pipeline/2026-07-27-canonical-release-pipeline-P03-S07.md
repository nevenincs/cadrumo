---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:4d9fc0cfc72e1dbe20c09793a310363ab7c0e877aef4aefff149e4d610314d54'
step_id: 'S07'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Delete the retiring upload workflow and its conformance test and sweep every reference, gate: rg -i pypi-upload across the tree returns only vault records and history, and uv run --no-sync pytest dev/release/tests -q passes clean after the deletion

## Scope

- `.github/workflows/pypi-upload.yml`
- `dev/release/tests/test_pypi_upload_workflow.py`

## Description

- Confirm the only non-vault references to the retiring lane are the workflow and its conformance test.
- Confirm neither path carries peer working-tree changes before touching them.
- Delete both files with a tracked removal.
- Run the reference sweep and the owning test suite as the Step's two gates.

## Outcome

Both files deleted in the commit subject `chore(release): retire the second PyPI
lane, its premise is void`. Cited by subject rather than by hash: the branch
history was rewritten after this record was written, so the original hash no
longer resolves. Subjects survive a rewrite; hashes do not.

Gate one: the tree-wide reference sweep returns no match outside the vault. The
records that document the retirement remain, which is what the gate expects.

Gate two: the release test suite passes at 150 tests, down from 155. The five
missing tests are exactly the deleted conformance cases, so the reduction is
accounted for rather than assumed.

The lane existed solely to deliver an owed prior-version PyPI upload for a
release whose promotion predated an armed publication gate. The operator ruled
that version abandoned on the finding that nothing has ever shipped end to end,
so the release it served was a partial artefact and never a delivery. Deleting
the lane executes the end state its own charter declared; only the trigger
condition collapsed, together with its premise.

Deletion is strictly stronger than the version pin the decision record first
considered: a deleted lane cannot be mis-dispatched, and its free-text release
tag input was prose rather than a mechanism.

## Notes

Scope boundary: the registry-side half of the retirement, the three trusted
publishing registrations and their environments, is an operator act recorded as
a decision point in the owning record and is deliberately outside this Step.

Sequencing note: this Step was taken ahead of the version-identity phase because
the semantic discovery service was mid-rebuild and its index was demonstrably
incomplete, which bars new-authority work under the standing discovery mandate.
A deletion cannot duplicate an authority that discovery failed to surface, so the
mandate's purpose is not engaged here. No other Step was started while the index
remained unusable.
