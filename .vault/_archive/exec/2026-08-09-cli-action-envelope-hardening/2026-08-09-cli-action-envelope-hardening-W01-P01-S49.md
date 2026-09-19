---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:74e6fddfd8ecc4b3f52225409000e7d9253f413601e2436ad0ca7f1941f45c71'
step_id: 'S49'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Expand migration Phases through the plan CLI with one exclusive Step per adjudicated producer cluster before execution

## Scope

- `.vault/plan/2026-08-09-cli-action-envelope-hardening-plan.md`

## Description

- Re-run the AST-backed action census against immutable `HEAD` and reconcile all
  1,254 candidates against the disposition ledger.
- Classify all 974 producer rows into exclusive existing or newly added migration
  Steps without overlapping file ownership.
- Strengthen the workflow and error-schema Steps to require deletion of permissive
  compatibility fields instead of adding parallel typed fields.
- Narrow the catch-all CLI renderer Step to the two remaining renderer-only files.
- Add one ledger-reconciliation Step and 32 missing producer-cluster Steps through
  the canonical plan CLI.

## Outcome

The plan now contains 94 Steps. Existing Steps plus the 33 additions cover all
974 adjudicated producer rows with zero uncovered producer clusters. The required
disposition reconciliation remains open as its own fail-closed Step, so the stale
ledger cannot be mistaken for migration completion.

## Notes

The disposition gate intentionally remains red until its dedicated Step removes 14
stale rows and adjudicates the three current candidates. Plan validation reports only
the expected non-monotonic identifier-order warning caused by appending canonical Step
ids into their owning earlier Phases.
