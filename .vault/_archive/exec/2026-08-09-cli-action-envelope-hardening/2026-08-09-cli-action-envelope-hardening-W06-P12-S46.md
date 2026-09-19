---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:6e71a15f00a3f8f7d869f1486e2af382536276d65de212187bb34fdac9d392b7'
step_id: 'S46'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---




# Require a complete semantic and mechanical pass with no newly discovered action site or alias

## Scope

- `dev/quality/cli_action_census.py`
- `dev/quality/cli_action_census_dispositions.py`
- `dev/quality/cli_action_census_dispositions.toml`
- `dev/tests/test_cli_action_census.py`
- `dev/tests/test_cli_action_census_dispositions.py`

## Description

- Regenerate the schema-v3 disposition ledger from the current-tree census through its canonical writer.
- Retire stale exception-owner observations and reconcile every live candidate to one grounded role.
- Reject missing, stale, duplicate, and unreviewed direct-flow aliases with mutation-sensitive gates.

## Outcome

Commits `2be1f36529`, `f42a65e588`, and final refresh `f8a9eb9523` reconcile an exact 196-row live partition after S75, S84, and S91: seven canonical owners, 20 producers, three transformers, and 166 grounded exclusions. All 41 former exception-owner rows remain retired because the live AST observation set is empty.

Canonical re-rendering is byte-identical to the TOML. The final combined census, disposition, authored-message, and closure selection passes 42 tests; Ruff, format, and diff checks pass.

## Notes

- Wizard `next_command` is a localized success-text hint and is grounded as excluded; the typed `next_action` declaration remains the canonical recovery authority.
- The final refresh removes five retired S75 continuation rows and two retired S91 command-prose rows and grounds the concurrently relocated TUI command literal at its live widget owner.
