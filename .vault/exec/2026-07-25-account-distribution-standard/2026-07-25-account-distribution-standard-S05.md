---
tags:
  - '#exec'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S05'
related:
  - "[[2026-07-25-account-distribution-standard-plan]]"
---




# DONE, with a finding. No cadrumo workflow declares a tag trigger, verified by parsing the trigger block of all fourteen workflow files rather than grepping them, so there was nothing to remove here and this step closes as already-conformant rather than as work performed. Converted into a regression gate so it stays true, publication must be dispatch-only and a tag filter on the publication authority now fails the suite. The defect this step was written for lives in the sibling products, and the removal instruction is carried in their migration references

## Scope

- `.github/workflows/publish-release.yml`
- `dev/release/tests/test_publish_release_workflow.py`

## Description

- Parse the trigger block of all fourteen workflow files and enumerate every declared event and tag filter.
- Confirm no cadrumo workflow declares a tag trigger.
- Add a regression gate requiring the publication authority to stay dispatch-only.
- Carry the removal instruction into the sibling products' migration references, where the defect actually lives.

## Outcome

This step closes as already-conformant rather than as work performed, and that distinction is stated rather than papered over. There was no tag trigger to remove: publication is `workflow_dispatch` only, and so is every other workflow in the tree except the three that legitimately run on push or pull request.

What was actually delivered is the regression gate. An inert tag filter on the one workflow that uploads to public channels is the most dangerous kind of dead configuration, because it reads to a maintainer as a second and automatic publication path while being unable to fire. The property was already true; it is now enforced.

## Notes

The triggers were enumerated by parsing each workflow as YAML rather than by grepping for a `tags:` key. A grep would have found the unrelated `keep_tags` input on the evidence-collection workflow and missed nothing else, but a clean grep result is not evidence unless the pattern fits the data's shape, and a tag filter can be spelled several ways.

The sibling verification is partial and is recorded as such. Both `vaultspec-core` publication workflows were read and are dispatch-only. The dashboard's release workflow trigger block was not read in full, so its status is neither confirmed nor excluded, and its migration reference says so rather than assuming.
