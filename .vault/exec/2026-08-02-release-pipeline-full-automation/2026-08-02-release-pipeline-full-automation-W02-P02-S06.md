---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:a060af0b66e1ff45eebfb70b19480b50c6c175ea54a042717fef5e74a2553ad4'
step_id: 'S06'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---




# Add the conclusion waiter as a bounded backoff poll with a declared budget and an instructive timeout refusal naming the run it was watching, sized as a cheap poll on a short-lived job rather than a busy hold, because a waiting orchestrator occupies one of four self-hosted runner slots shared across products for the whole campaign it watches, gate: uv run --no-sync pytest dev/release/tests/test_run_resolution.py -q passes covering success, failure, cancellation, and budget-exhaustion outcomes against an injected clock with no real sleeping

## Scope

- `dev/release/run_resolution.py`
- `dev/release/tests/test_run_resolution.py`

## Description

Added the bounded exponential-backoff `_poll_until` primitive plus `wait_for_run` (resolution retry) and `wait_for_conclusion` (run-status poll), both driven by injectable `now`/`sleep` callables. Production defaults to real `datetime.now(UTC)`/`time.sleep`; tests inject a deterministic fake clock whose `sleep()` advances its own `now()`, proving budget-exhaustion timing with zero real waiting. `PollBudget` declares `total_seconds` plus interval bounds and backoff factor explicitly, validated at construction. `wait_for_conclusion` returns a `RunOutcome` for any terminal conclusion (success/failure/cancelled) without judging it — interpretation is left to the orchestrator — and raises `RunResolutionError` naming the run id, workflow path, and html_url on budget exhaustion.

## Outcome

Gate green: same test file. `test_wait_for_conclusion_reports_every_terminal_conclusion` (parametrized success/failure/cancelled) and `test_wait_for_conclusion_exhausts_its_budget_and_names_the_watched_run` cover this Step directly; the full file (26 tests) passes with no real sleeping anywhere.

## Notes

No incidents. Landed in the same commit as S05 (one module, one test file, shared gate).
