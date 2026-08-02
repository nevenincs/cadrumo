---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:c81046b5bd4ac3fd92c53bbc3c81ce2b97d4c71f7b757c23a264d3ece4828f99'
step_id: 'S05'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Build the dispatch-and-resolve module that dispatches one workflow and then resolves the run IT started, keyed on the workflow path, the head commit, and a created-after timestamp captured before the dispatch, refusing on ambiguity rather than guessing, because gh workflow run returns no run id and the smoke workflow queues rather than cancels so the newest run may belong to a neighbour, gate: uv run --no-sync pytest dev/release/tests/test_run_resolution.py -q passes over injected Actions API payloads including a planted competing run started between the dispatch and the poll, and the resolver refuses rather than promoting the neighbour

## Scope

- `dev/release/run_resolution.py`
- `dev/release/tests/test_run_resolution.py`

## Description

Built `dev/release/run_resolution.py`: `dispatch_workflow` fires `gh workflow run` (returns nothing, since gh yields no run id). `resolve_dispatched_run` matches the run one dispatch started by workflow path, head commit, the workflow_dispatch event, and a created-after timestamp captured before dispatch. Zero matches raise `RunNotYetVisibleError` (retryable). More than one match raises `RunResolutionError` naming every candidate id — the identify-MY-run hazard, refused rather than guessed. `dispatch_and_resolve` composes both, capturing `created_after` itself immediately before dispatching.

## Outcome

Gate green: `uv run --no-sync pytest dev/release/tests/test_run_resolution.py -q` — 26 passed. Coverage includes `test_wait_for_run_refuses_immediately_when_a_competing_run_appears_between_dispatch_and_poll`, which plants a competing run alongside the dispatch's own run in the same poll snapshot and proves the resolver refuses rather than promoting either candidate.

## Notes

No incidents. A pre-commit ruff-format hook reformatted a nested `with` block in the test file after the first commit; landed as a follow-up formatting-only commit.
