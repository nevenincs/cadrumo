---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:aa7d3aea1d6e1ac1b96f495105f616d88f9b4ffb64a4b99992462ed190b5b2d3'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# `secure-storage-performance-hardening` `W01.P02` summary

The phase delivered a reusable two-process CLI profiler, noise-resistant
calibration and budgets, a complete source-bound pre-optimization baseline,
and planted proofs that the profiler and live census fail on the regressions
they govern.

- Modified: `src/cadrumo/tests/cli_performance.py`
- Created: `src/cadrumo/tests/test_cli_performance.py`
- Created: `src/cadrumo/entrypoints/cli/tests/test_cli_performance_calibration.py`
- Modified: `src/cadrumo/entrypoints/cli/tests/test_cli_performance_budgets.py`
- Created: `dev/benchmarks/cli/capture_baseline.py`
- Created: `dev/benchmarks/cli/test_capture_baseline.py`
- Created: `dev/benchmarks/cli/README.md`
- Created: `dev/benchmarks/cli/baseline.census.json`
- Created: `dev/benchmarks/cli/baseline.json`
- Created: `dev/benchmarks/cli/baseline.raw.json.gz`
- Created: `dev/benchmarks/cli/current-source-delta.md`

## Description

Resolution and invocation run in independent fresh interpreters and report
latency, imports, model construction, filesystem deltas, native filesystem
operations, and storage-call instrumentation without mixing machine evidence
with CLI output. Calibration uses warmups, at least three measured samples,
alternating command/control order, medians, dispersion, and independent
absolute and control-ratio budgets.

The frozen baseline enrolled all 361 nodes in its source snapshot and 100
controls, retaining authenticated lossless observations and an independent
exact-set census with zero failures or timeouts. It documents current-source
drift honestly instead of treating historical completeness as live freshness.
The profile-list symptom measured approximately 10.5 seconds at baseline and
showed import/model/storage work as the dominant signal for later Waves.

Permanent adversarial tests inject live registry imports and exact
storage-root materialisation after observation starts in both resolution and
safe-help processes. Separate specimens prove that newly introduced roots,
helper-generated groups, and leaves cannot arrive without execution policy.
Every Step received independent review; the final review reported no open
findings. Phase verification includes scoped Ruff and `ty`, unit and
integration profiler suites, deterministic baseline integrity checks,
coherent missing/invented-node negative tests, and the feature-scoped
Vaultspec gate.
