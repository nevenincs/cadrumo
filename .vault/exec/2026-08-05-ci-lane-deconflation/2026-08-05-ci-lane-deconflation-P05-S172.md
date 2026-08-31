---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:ad352e65b0bb5e924a72bd2eddbaa5a8a7e3f08755b19275eedca71cbe007df4'
step_id: 'S172'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in registration.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/user_profile/registration.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S172.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s172-execution-self-review-audit.md`

## Notes

- This is a stale-plan reconciliation with no source refactor or source provenance claim. The target is 348 raw physical lines and has no live module or callable size-budget subject.
- The sole peer-owned target change is the import relocation `..evidence._profile_legal_hold` -> `..evidence.profile_legal_hold`; it was preserved and explicitly excluded. The related test surface may also be peer-modified, so no test was run and no test pass is claimed.
- No source, plan, baseline, threshold, `--write-baseline`, `--accept-growth`, or default-index mutation occurred during this reconciliation.
