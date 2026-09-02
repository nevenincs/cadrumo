---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:9194389cb405c5af38056d5d2a572273afdbace5e3d8d433a623a222002cc834'
step_id: 'S10'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Retire the orchestrator, publication and soak workflows with their release-candidate modules

## Scope

- `.github/workflows/release-orchestrator.yml`

## Changes

D .github/workflows/release-orchestrator.yml
D .github/workflows/publish-release.yml
D .github/workflows/release-soak-promoter.yml
D dev/release/release_candidate.py
D dev/release/run_resolution.py
D dev/release/seal_candidate.py
D dev/release/soak_promoter.py
D dev/release/tests/test_publish_release_workflow.py
D dev/release/tests/test_release_alerting.py
D dev/release/tests/test_release_candidate.py
D dev/release/tests/test_release_orchestrator_workflow.py
D dev/release/tests/test_run_resolution.py
D dev/release/tests/test_soak_promoter.py
D dev/release/tests/test_soak_promoter_workflow.py
M .github/workflows/publish.yml
M dev/ci/tests/test_self_hosted_fleet.py
M dev/deploy/tests/test_docs_publish_workflow.py

## Notes

The per-job polling exemption in the self-hosted gate named two jobs of the retired
orchestrator, so it is removed; the workflow-level split covers the release path.

`dev/release/alerting.py` survives because the documentation delivery workflow still
invokes it, but its gate asserted which release-path workflows carry an alert job and
had no subject left once those three were deleted. It is retired with them, so the
alerting module's remaining consumer is currently ungated. That coverage gap is real
and is not closed by this Step.

The publish workflow gained a checkout in its upload job: the toolchain pin gate
requires the repository's own interpreter pin to be readable before the toolchain is
set up.
