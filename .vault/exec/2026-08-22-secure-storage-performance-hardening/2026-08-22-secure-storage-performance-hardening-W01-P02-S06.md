---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:dc29e80e8562983ece81bb4a925713ab47449b2dc4003b4ac538f965a80f680f'
step_id: 'S06'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Add quiet-runner calibration and median and ratio budget support without single-sample pass conditions

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_cli_performance_budgets.py`

## Description

- Add a policy requiring at least one warmup and three independently measured
  samples, with a five-sample default.
- Pair each command measurement with the stable root `--version` quiet control
  and alternate which side runs first.
- Retain every measured profile and summarize resolution and invocation with
  medians, median absolute deviation, and explicit control ratios.
- Evaluate composable absolute-median and control-ratio budgets with typed
  violations and threshold-exceeding samples.
- Reject timeouts, missing envelopes, child exceptions, and nonzero exits
  before any observation reaches an aggregate.
- Add arithmetic and real-process gates for minimum sampling, slow-majority
  rejection, absolute/ratio independence, warmup exclusion, fresh PID
  identity, alternating order, and failure refusal.
- Resolve the independent review's medium orchestration-coverage finding and
  obtain an approved re-review.

## Outcome

Quiet-runner calibration is now a reusable typed layer over the S05 profiler.
It cannot pass from a single lucky observation, exposes both phase-relative
ratios, and preserves the raw measured pairs needed to diagnose outliers and
runner noise. Six unit tests passed in 0.31 seconds. Three bounded real-process
calibration tests passed in 31.25 seconds; independent re-review repeated them
in 24.29 seconds. The existing six profiler integration tests also passed in
70.12 seconds. Scoped Ruff and `ty` checks passed.

## Notes

The first review found that the initial permanent tests covered only statistics
and budget arithmetic. The remediation added real calibration orchestration
coverage without mocks, fakes, injected runners, skipped tests, or a broad S07
baseline capture. A concurrent peer commit included the initial budget test
module while S06 was in progress; the final S06 commit remains exact-path and
records that shared-worktree attribution rather than rewriting history.
