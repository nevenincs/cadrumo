---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:13e2cf3b9fea0d2c151e057f120a3c548f07209723b2f54d6767ea197d57d70f'
related: []
---

# `secure-storage-performance-hardening` audit: `S06 quiet-runner calibration review`

## Scope

Independent review of W01.P02.S06 against the accepted performance ADR, its
research/reference grounding, the S05 fresh-process profiler contract, and the
S06 plan Step. The review covered fresh-process independence, warm-up and sample
statistics, paired-control ordering, absolute and relative budget semantics,
typed results and threshold outliers, explicit child failure handling, and the
automated bite proof. A real three-sample calibration smoke was also run.

## Findings

### calibration-orchestration | medium | The permanent tests do not exercise the calibration path

`test_cli_performance_budgets.py` verifies distribution and budget arithmetic,
including the required single-fast-sample negative, but never calls
`calibrate_cli_path`. Consequently the gate would remain green if later edits
stopped discarding warm-ups, reused child processes, removed command/control
order alternation, admitted a nonzero invocation, or failed to turn a timeout or
missing envelope into an explicit calibration failure. The current
implementation behaved correctly in a real smoke: three retained command
profiles and three controls used twelve distinct child PIDs, both phases exited
successfully, and finite median ratios were produced. That one manual
observation is evidence for the current revision, not a regression gate.

No critical or high findings were identified. The implementation otherwise
uses independent S05 profiles, alternates whole command/control pairs, requires
one or more warm-ups and at least three retained samples, evaluates absolute and
ratio limits independently, and retains typed violations plus samples exceeding
the strictest applicable threshold.

#### Resolution

Resolved in the S06 remediation. `test_cli_performance_calibration.py` now
drives `calibrate_cli_path` through real subprocesses. The success lane proves
warm-up exclusion, the exact three retained command/control pairs, alternating
measured order, twelve distinct phase PIDs, successful observations, and finite
ratios. Separate real-process lanes prove timeout and nonzero invocation
outcomes raise before aggregation. Independent re-review ran the integration
file explicitly with the integration marker and serial execution: all three
tests passed. The six arithmetic tests also passed in the default unit lane.
No finding remains open.

## Recommendations

Before S06 closes, add a permanent calibration-level test using the real
fresh-process profiler. Assert warm-up exclusion, exact retained sample counts,
unique resolution/invocation PIDs across command and control profiles, and
successful finite distributions. Add deterministic failure-path coverage that
proves nonzero and timeout observations cannot enter a distribution. Keep the
existing single-fast-sample negative and arithmetic tests.

Implemented and verified; no further S06 recommendation remains.
