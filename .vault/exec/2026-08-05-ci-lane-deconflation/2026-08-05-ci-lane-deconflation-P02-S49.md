---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:7c321c5d024d2d2dc2b3c72b8b22c7a1e9c66e9c0845b7ffde8145038e1fa4f4'
step_id: 'S49'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Flip continue-on-error off the per-push integration conformance step after the action-envelope campaign is audited complete and the unchanged authoritative four-module recipe is green. Closure evidence: the historical 2026-08-13 baseline was 6 failures among 48 then-collected tests, current suite evolution legitimately collects 46, all 46 pass, and the workflow remains pinned to the exact recipe with eight workers. The denominator is an observation, not a permanent release condition

## Scope

- `.github/workflows/ci.yml and dev/ci/tests/test_ci_workflow.py`

## Description

- Removed the four dead runnable-command citations from retained profile payload
  schema docstrings without registering retired verbs or weakening the live-tree
  conformance scanner.
- Re-ran the unchanged four-module per-push integration recipe and established a
  current green baseline of 46 collected tests. The historical 48 was an
  observation of the older suite, not a durable denominator.
- Removed `continue-on-error: true` from the named per-push integration
  conformance step while preserving its exact eight-worker recipe delegation.
- Added workflow conformance coverage requiring the named step to remain
  blocking.

## Outcome

The per-push integration conformance step now fails the workflow when its
authoritative recipe fails. The action-envelope prerequisite is closed and the
current recipe is green at 46 of 46.

## Notes

- Historical baseline: 6 failures among 48 tests on 2026-08-13.
- Current verification: `just test-per-push-integration-gates` passed 46 tests;
  the two focused workflow-conformance assertions passed; scoped Ruff, format,
  and diff checks passed.
- VaultSpec RAG located the live profile command-spec authority and confirmed
  that the four payload schemas preserve retired-surface evidence. No command
  declaration or competing authority was introduced.
- The workflow and primary conformance assertion landed concurrently in shared
  commit `04ea7186d05`; the remaining local test edit is formatting-only.
