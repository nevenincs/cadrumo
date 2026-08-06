---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:fce3328c0019b5bfce07b695ead9bedb51593bbbb43378ba800b8cb365703f9c'
step_id: 'S33'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Reject stale skipped ambient mismatched and incomplete release evidence

## Scope

- `dev/release/tests/test_distribution_readiness.py`

## Description

- Build real temporary Git repositories and complete release-cohort manifests through
  the production cohort authority.
- Execute an actual installed-oracle process and persist its result through the
  production evidence writer.
- Exercise complete, missing, failed, different-cohort, older-commit, skipped-status,
  ambient-executable, and missing-client-identity cases through release readiness.
- Avoid mocks, patches, monkeypatches, fakes, stubs, skips, and duplicated readiness
  logic.

## Outcome

- A complete current-cohort set passes when evaluated against its exact checked-out
  commit and declared row set.
- Missing or failed rows, changed source commits, other cohort bytes, skipped status,
  ambient execution, and absent real-client identity all produce blocking verdicts.
- The tests use real files, real Git commits, production schemas, content-addressed
  evidence, and an actually executed subprocess.
- The new evidence-set module contributed seven passing cases; the combined readiness
  suite passed all 33 tests with formatting, Ruff, and type checks clean.

## Notes

- The unit acceptance set narrows the required-row parameter to the current platform so
  it never fabricates cross-platform execution. Production retains the full twelve-row
  blocking matrix.
