---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:22a5f5d70a712f3b7a0e704626b8bb657153c2fe3ea58b9da4668a50450d0feb'
step_id: 'S107'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Declare the standing mutmut scope and cadence from measured cost

## Scope

- `.vault/adr/2026-09-07-quality-gate-zero-closure-blind-green-gates-adr.md`

## Outcome

The accepted ADR declares a manual, verify-only, one-detector-at-a-time mutation scope. A run is triggered after a detector implementation, paired gate, or shared mutation-selection/copy configuration changes, before closing the corresponding implementation Step. Unchanged detectors have no calendar rerun.

Accepted bounded detector runs currently span approximately 58.2 seconds for the taxonomy detector through 1054.75 seconds for the verdict detector. Those observed costs support the change-triggered cadence and rule out commit-time, whole-suite, and automatic CI mutation execution. No hook, workflow lane, or `justfile` command is installed by this campaign. A future manual wrapper or dispatched job remains with the owner of those surfaces.

Every survivor is triaged as an individual finding or an inert equivalent. No mutation score is calculated, targeted, or reported.
