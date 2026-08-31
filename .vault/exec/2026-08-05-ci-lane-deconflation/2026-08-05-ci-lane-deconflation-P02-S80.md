---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:4bbc8ce2a9a77ad44b7dbfeff852dbe99d489ad88b346b18555418db9ff5d36b'
step_id: 'S80'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Discard a broad calculations-and-registry measurement as INVALID rather than report its failure list, and re-run it clean.

## Scope

- `src/cadrumo/application/calculations/cross_period_clean_state.py`
- `src/cadrumo/application/calculations/tests/_cross_period_clean_state_support.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S80.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s80-execution-self-review-audit.md`

## Notes

- No literal historical process output is recoverable: Git and current vault records contain neither the discarded command nor a terminal pytest summary or failure list. The plan row is the surviving lifecycle account, not a test receipt. This record therefore reports no discarded output, re-run, import receipt, or clean remeasurement.
- The two scope paths changed in mixed peer commit `2688c6b4e02f5f1b189d6a32c8684c96eadd2b77`; their interleaving with the broad run is why S80 invalidates that measurement rather than attributing failures to code. Later `9bc7c757c2d` VIGENTE-only fixture selection and its S82/S87 verification are downstream work, not S80 evidence. Current evidence extraction has since moved into `_cross_period_external_evidence.py`; no current-source result is claimed here.
- No pytest command was run for this documentation-only reconciliation while another measurement remains active.
