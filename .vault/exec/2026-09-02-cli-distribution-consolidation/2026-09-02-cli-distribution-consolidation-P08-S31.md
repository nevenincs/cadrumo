---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:59e3c3ed51e95d05ad69229dfebd6568d7fcbeb13eba33a5ea919621f3245bc7'
step_id: 'S31'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Delete the control-plane document and restate its sizing rule at the call sites

## Scope

- `.github/ci-control-plane.md`

## Changes

D .github/ci-control-plane.md
M dev/ci/tests/test_machine_aware_load.py
M dev/docs/sequence_build_gate.py
M dev/docs/tests/test_sequence_goldens.py
M dev/docs/tests/_sphinx_build_harness.py
M justfile

## Notes

Six sites cited the document for one fact - that runners share machines with other
repositories' runners, so a pool is sized for co-residency rather than for the whole
box. Each now states it where the sizing decision is made.
