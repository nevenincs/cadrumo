---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:350ab4208ab767ff16bb5f91e74d0887028a35baaa8dcce61833c5230f09995a'
step_id: 'S52'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Stop feeding the packaging-claude acquisition lane run id into the operator-minted claude evidence-release input, and carry the real evidence-release tag onto the sealed candidate instead

## Scope

- `.github/workflows/release-orchestrator.yml`
- `dev/packaging/publication_inputs.py`
- `dev/release/seal_candidate.py`
- `dev/release/tests/test_release_orchestrator_workflow.py`
- `dev/packaging/tests/test_publication_inputs.py`

## Description

- Emit the VERIFIED evidence-release tag as an output of the precondition job that checked it.
- Source the seal stage's `CLAUDE_EVIDENCE_RELEASE` from that output and add `precondition` to the seal's needs.
- Refuse a bare-integer value in `seal_candidate`, since a run id can never be a release tag.
- Add the required negative assertion, a provenance assertion, a module-guard test with a control, and a claimed-`claude-plugin` separation test.
- Correct the S45 assertion that encoded the mis-wiring as correct.

## Outcome

482 passed across `dev/release/tests`, the derivation suite, `dev/deploy/tests`, and `dev/ci/tests`. Lint and `ty check` clean on my files.

## Notes

The finding is correct and the fix I shipped in S45 was worse than the bug it closed. S45 fixed dropped ids by wiring every acquisition output through to the seal, and in doing so fed `claude_plugin_run_id` into `CLAUDE_EVIDENCE_RELEASE`. Those are different facts. The publication authority consumes that input with `gh release download "$CLAUDE_EVIDENCE_RELEASE"`, so a run id there fails at the final leg AFTER a full 48-72 hour soak - and, worse, silently replaces the operator-minted evidence the precondition job had just verified with a machine-produced value. That is the evidence-integrity violation the host-extension ruling exists to prevent: the four claude-* rows assert a real client installed real bytes, and substituting a workflow's run id asserts the same sentence about a different event.

What makes this uncomfortable rather than merely wrong is that the contract I violated is one I wrote. `LANE_WORKFLOW_BY_CHANNEL`'s docstring states the two "must never collapse into one input", with the reason spelled out. I had the rule in front of me, in my own words, and the mechanical task of "wire the outputs through" did not prompt me to re-read it - the field names looked adjacent, and adjacency was enough.

The test that let it pass is the same shape the audit keeps finding in my work. `test_every_acquisition_run_id_reaches_the_seal_stage` asks whether ids are DROPPED and never asks what a field semantically IS, so it was blind by construction to a value being present but wrong. Worse, its assertion listed `CLAUDE_EVIDENCE_RELEASE -> claude_plugin_run_id` explicitly, so it did not merely miss the bug, it PINNED it. That test is now corrected with the reason recorded inline, and the gate's required negative assertion is what replaces it.

Three layers now, deliberately, because the workflow assertions only pin today's wiring:

- The evidence tag is emitted by the job that VERIFIED it, so a sealed candidate can only name a release the precondition actually checked.
- `seal_candidate` refuses a bare-integer value outright, making the mistake unrepresentable from any caller and failing at seal time rather than after the soak.
- The refusal test carries a control proving a genuine tag is NOT refused, so the guard cannot rot into one that rejects everything.

## Attributed, not absorbed

`ruff check` reports 7 D103 findings in `dev/packaging/tests/test_publication_inputs.py`. All 7 are present at HEAD before this change and belong to the P02 lane; the test added here carries a docstring.
