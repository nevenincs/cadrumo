---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:acf86b66f5cc5282b43c5ca1ea8d89d491cd0e4b1c2d67c80f6e3458f84dd3d9'
step_id: 'S88'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Replace residual root CLI recovery prose with canonical actions and explicit no-action outcomes

## Scope

- `src/cadrumo/entrypoints/cli/_log_levels.py`
- `src/cadrumo/entrypoints/cli/_app_diagnostics.py`
- `src/cadrumo/entrypoints/cli/_app_diagnostics_telemetry.py`
- `src/cadrumo/entrypoints/cli/_app_maintenance.py`
- `src/cadrumo/entrypoints/cli/_app_live.py`
- `src/cadrumo/entrypoints/cli/tests`

## Description

- Resolve diagnostics no-run states to the registered ledger-classify action while retaining factual notices.
- Resolve live truncation/refused-pair continuations and maintenance reconciliation through catalogue actions.
- Remove duplicate retry and LLM-classification command prose.
- Give invalid environment log levels an explicit canonical no-action operator-decision contract.
- Classify the closed native parse-validation set separately from post-dispatch recovery.
- Remove obsolete profile-export/suggestion tests for the deleted command surface.

## Outcome

The exact root producer population is 16 direct notices plus four diagnostics helper callers. Genuine continuations resolve `operator.ledger.classify`, `operator.live.filed.pull_all`, or `operator.maintenance.reconcile`; invalid `CADRUMO_LOG_LEVEL` carries an exact no-action verdict. Mutually exclusive flags and five immediate live option-shape failures remain durably classified as native parse validation.

Recovery command prose and direct verdict/action construction are absent. The complete focused selector passes 63 tests and the maintenance module passes four. Ruff and diff checks pass. Independent review confirmed that removing the two retired profile-export tests loses no live reconcile coverage.

## Notes

- Portal error propagation was split to and closed by S105; retired lazy optional-extra placeholder machinery was already absent and removed from this reconciled scope.
