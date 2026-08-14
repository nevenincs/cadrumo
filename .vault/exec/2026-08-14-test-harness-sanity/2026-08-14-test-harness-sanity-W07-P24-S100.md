---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:95837af90569f83cf48625b10a10792403320fe1e03e975634b95e2dd4a549c0'
step_id: 'S100'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Delete the private justfile parsers in the CI gate modules and consume the lane authority

## Scope

- `dev/ci/tests/test_machine_aware_load.py`
- `dev/ci/tests/test_ci_workflow.py`

## Description

- Delete the private recipe, marker, template and exclusion parsing from both gate modules.
- Derive the enrolled member list from the recipe that runs it, as a union across that recipe's lanes.
- Replace the hand-written member tuple with the same derivation.
- Rebuild the recipe-shape checks on the renderer's resolved commands instead of raw text.
- Retain one real collection control grounding the static model against actual selection.

## Outcome

Both gates now ask the authority what a lane reaches and what it excludes, instead of re-deriving it from the build file. One gate had rendered the recipe through a mode that does not resolve variables, so it was comparing source text while describing it as the rendered recipe; it now reads resolved commands. The other kept a third hand-written copy of the member list, which is gone. Forty-seven cases pass across the two modules.

The member derivation takes the union of every lane belonging to the enrolling recipe rather than its longest lane. A member that is preflighted alone but silently dropped from the combined run line would be invisible to a longest-lane reading, and the mutation that removes exactly one member proves the union catches it while the alternative would not have.

## Notes

One piece of parsing was deliberately kept rather than migrated. The worker-count check resolves what a specific call site's width argument becomes, including a per-invocation environment override, and the authority resolves variables globally with no notion of a per-call-site override. Folding that into the shared record would have made the shared record answer a question it cannot answer correctly, so the local parsing stays with its reason stated. Not all repetition is duplication, and the test for which is whether one implementation can answer both questions truthfully.

Two agents collided on the same file mid-write and produced a duplicated import line. The collision was noticed and reverted, but it is worth recording that concurrent edits to one file in a shared tree produce artefacts that look like content.
