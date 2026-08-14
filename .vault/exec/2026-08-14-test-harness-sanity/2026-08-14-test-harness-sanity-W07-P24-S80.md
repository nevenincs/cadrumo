---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:d67ec55a156dc2da67bcebf2a3f05329b89671708b221ed9f133c3eee8477ed6'
step_id: 'S80'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Move installed-hook worker-pool proofs out of routine unit execution

## Scope

- `src/cadrumo/tests/test_worker_count_hook.py`

## Description

- Move the four installed-hook xdist subprocess proofs into an integration-marked harness module.
- Retain the twelve pure worker-replacement detector cases in the routine unit module.
- Update the canonical harness recipe and CI membership contract to select the real-process module explicitly.

## Outcome

Routine unit selection now runs twelve bounded detector tests without starting nested worker pools. The dedicated harness selects four real xdist proofs non-vacuously and runs them outer-serially; all four pass in the focused harness-only run.

## Notes

Ruff, formatting, unit execution, explicit integration execution, recipe dry-run, CI contract tests, diff integrity, and independent review passed. The combined harness proceeds through all worker proofs and then reports the separate full-corpus failure recorded by `S81`; no aggregate green claim is made.
