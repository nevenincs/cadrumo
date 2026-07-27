---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S07'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-release-pipeline with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-07-27-canonical-release-pipeline-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Delete the retiring upload workflow and its conformance test and sweep every reference, gate: rg -i pypi-upload across the tree returns only vault records and history, and uv run --no-sync pytest dev/release/tests -q passes clean after the deletion and ## Scope

- `.github/workflows/pypi-upload.yml`
- `dev/release/tests/test_pypi_upload_workflow.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

Both files deleted in commit `e028be1a9e`.

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
