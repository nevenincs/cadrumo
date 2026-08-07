---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:708438bc138595d6a016d215060c672534b5df80532fc426eaba155e6fba530b'
step_id: 'S31'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W05.P07.S31

## Outcome

Classified: **a load artefact, not a regression.** The same test fails inside the full serial lane and passes when run alone.

## The measurement

- Inside `pytest src/cadrumo -m serial -n0`, running as the first of 54 tests on a box carrying the agent fleet: `test_iva_quarterly_aggregation_partitioned_p95_cpu_within_budget` **FAILED**.
- Running `test_ledger_scale_benchmark.py` as its own module: the same test **PASSED**, alongside 6 of its 7 siblings.

The budget is a P95 CPU-second bound, so it measures a quantity contention directly inflates. The Step's hypothesis — measured 3.906 CPU-s against a 3.0 budget on a box that ran a large agent fleet all night — is the shape confirmed here.

## The caveat that keeps this honest

This is a confirming result for the prior, so it deserves a plausibility check rather than acceptance. The "isolated" run was **not** taken on a quiet box: the peer fleet was active throughout and this session had suites running minutes earlier. So the comparison is not loaded-versus-quiet, it is whole-lane-versus-single-module.

That the budget is met even under residual load argues for real headroom rather than a marginal pass, which strengthens the classification. But a genuinely quiet baseline was not available, and this record should not be read as having established one. If the test fails again on a quiet box, this classification is wrong and the budget or the code is the problem.

## Not actioned

No budget was relaxed. Widening a threshold to accommodate contention is how a perf gate stops measuring anything, and the evidence here says the gate is right and the environment was loaded.

## Incidental finding, not mine

The sibling `test_modelo_calculate_reports_latency` fails on a peer's **uncommitted** working-tree edit to `_data/registry/cadrumo/user_profile/schema.toml`: a field description exceeds the 512-character schema bound, so `load_user_profile_schema` raises. HEAD's version loads cleanly. Left untouched per `uncommitted-wip-is-not-orphaned`, and reported rather than fixed.
