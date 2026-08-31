---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:ab98066096a79b5f2a5eaf82010e8c0c1b19998c0f186cfef9d5a952d818f3a9'
step_id: 'S97'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
#

## Scope

- src/cadrumo/application/registry/tests/test_temporal_coverage.py

## Changes

- A .vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S97.md
- erify: pytest -q -n0 src/cadrumo/application/registry/tests/test_temporal_coverage.py::test_temporal_coverage_expands_open_selectors_through_the_supported_horizon -> 1 passed in 55.58s

## Notes

Immutable provenance for the original positional open-selector test is 915a66a5bc; immutable provenance for the subject correction is e1ad83404. Neither supplies recoverable historical literal pytest output. S98 is the coupled completion: it corrected the remaining multi-revision composition assumption exposed after S97 selected the right open revision. This record attests only the fresh focused receipt above.
