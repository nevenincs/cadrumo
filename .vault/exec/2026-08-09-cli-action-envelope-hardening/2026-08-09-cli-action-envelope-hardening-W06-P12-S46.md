---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:6ef9525081f112412ad65fc0dc7d5b634889cad873c1e4026176a130a643b53e'
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

Commits `2be1f36529` and `f42a65e588` reconcile an exact 203-row live partition: eight canonical owners, 23 producers, four transformers, and 168 grounded exclusions. All 41 former exception-owner rows are retired because the live AST observation set is empty.

Canonical re-rendering is byte-identical to the TOML. The complete census/disposition selection passes 30 tests, with seven additional authored-message join proofs passing; Ruff, format, and diff checks pass.

## Notes

- Wizard `next_command` is a localized success-text hint and is grounded as excluded; the typed `next_action` declaration remains the canonical recovery authority.
