---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:65809f2f130aa653f09bff49db4e6f695d03d39efea24d22c15a892013285c03'
step_id: 'S25'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Wire the host-extension evidence precondition into the orchestrator entry so a claimed claude channel with no operator-minted evidence release refuses the whole chain before the bump lands rather than after a version is burned, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting the precondition job precedes the bump job in the needs graph

## Scope

- `.github/workflows/release-orchestrator.yml`
- `dev/release/tests/test_release_orchestrator_workflow.py`
- `dev/packaging/publication_inputs.py` (mode added in S24's commit)

## Description

- Wire the `precondition` job as the first real gate, needing only `preflight`.
- Add `precondition` to the bump job's needs, so no version is computed until the gate clears.
- Add three conformance tests covering the needs-graph ordering, the never-mint property, and the live descriptor.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q` reports 17 passed and `dev/ci/tests` 14 passed.

## Notes

The ordering assertion is on the NEEDS GRAPH, not on step order within a job, because that is where the property actually lives. A precondition that ran late would still refuse correctly - it would simply refuse after the bump had already landed a commit, a tag, and a burned version. The identity ledger burns versions permanently, so that cost is unrecoverable, and the whole value of this gate is that the refusal is knowable at entry and therefore free.

The second test asserts an absence with a specific target: the orchestrator must never invoke `emit_real_client_evidence`. This is the one place in the pipeline where full automation is deliberately refused. The four `claude-*` rows assert that a real client installed real bytes; the emit guard refuses SDK-driven runs by design, so a workflow that minted them would assert the same sentence about a different event. Automating them would not speed the pipeline, it would make it lie.

The live-descriptor test pins that the CURRENT tree passes, so a red there reads as "the descriptor changed" rather than "the code broke". The refusal path's positive control lives in the owning module's own tests, where the descriptor can be varied; duplicating it here would test the fixture rather than the wiring.
