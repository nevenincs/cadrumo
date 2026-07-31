---
tags:
  - '#exec'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:75f7c18fed700d379f065fffd856be11f8a4d3c22e5ae6912b06f5a30df71703'
step_id: 'S02'
related:
  - "[[2026-07-25-account-distribution-standard-plan]]"
---

# DONE in this tree, BLOCKED externally. The publication authority now lands both the cadrumo formula and the cadrumo bucket manifest in the one shared account repository, each push staging exactly its own product-scoped path, so a second product is one more formula file plus one more manifest file and creates nothing. Proven by a conformance predicate over the parsed workflow with a real negative control, the predicate rejects the pre-change in-repository push on its content and five substantive properties are rejected against the pre-change workflow, so the gate is not vacuous. The files cannot actually land until the operator creates nevenincs/homebrew-tap, which returned 404 on a structured query at 2026-07-25

## Scope

- `.github/workflows/publish-release.yml`
- `dev/release/tests/test_publish_release_workflow.py`

## Description

- Retarget the Scoop push from the product's own repository to the shared account repository, using the same variable and secret the tap push already used.
- Rename both steps to name the shared repository rather than the product's own.
- Factor the shared-repository safety properties into a conformance predicate over the parsed workflow.
- Replace the assertion that Scoop needs no channel credentials, which the supersession made false, with one that no channel push writes to a product repository's default branch.
- Rewrite the operator-preflight refusal text, which still instructed the superseded topology.

## Outcome

A second product lands as one more formula file and one more manifest file, with no restructuring. Both pushes stage exactly their own product-scoped path, so a sibling's file is never touched.

The acceptance predicate is proven non-vacuous rather than merely asserted. Run against the pre-change workflow it rejects the in-repository Scoop push on its content, and five substantive properties are rejected in total across both pushes: shared-repository targeting, and the backward-bump guard and lost-race retry on each. Seven unsafe push shapes, including the literal pre-change shape, are pinned as parametrised rejection cases, and one safe shape is pinned as acceptance so the predicate is discriminating rather than always-failing.

## Notes

The first negative control run was weak and was replaced. Pointing the acceptance tests at the pre-change workflow made all five fail, but they failed on the step-name lookup rather than on the design, because the steps had been renamed. A rename is not a safety property. The predicate was refactored out of the tests so it could be driven directly against the pre-change push bodies, which is what produced the substantive result.

That second run also produced an honest partial: the pre-change Homebrew push is ACCEPTED by the staging predicate, correctly, because the tap was already shared and already staged only its own path. Nothing about Homebrew staging changed; what changed there is the guard and the retry, which their own tests reject. The predicate has teeth exactly where the design changed and is silent where it did not, which is the correct behaviour and not a gap.

A real detector hole surfaced while doing this. Moving both pushes inside a retry `if` dropped them out of the publish-verb confinement scan, because that scan treated only line-start and shell operators as command positions. A `git push` written as `if git ... push` in a read-only job would have evaded the gate. The command-position pattern now admits shell keywords, and four such spellings are pinned as non-vacuity cases. This was found by an assertion failing for the wrong reason and being investigated rather than adjusted.

The files cannot land until the operator creates the shared repository, which returned 404 on a structured query.
