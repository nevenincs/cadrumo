---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:ee57dacc23ce52d05a4fe9a4809e999652c22144622fcef426a75cd46c3dc298'
step_id: 'S120'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Derive and exclusively partition the registered-error authored-message join

## Scope

- `dev/quality/cli_action_census.py`
- `dev/quality/cli_action_census_dispositions.py`
- `dev/quality/cli_action_census_dispositions.toml`
- `dev/tests/test_cli_action_census.py`
- `dev/tests/test_cli_action_census_dispositions.py`
- `dev/tests/test_authored_error_message_join.py`

## Description

- Join live registered error codes to authored constructor-message sites using a static AST scan.
- Resolve named and lazy package-facade re-exports without importing production modules.
- Partition every discovered site into clean, one exact exclusion, or exactly one registered owner.
- Reject unresolved aliases, stale exclusions, missing owners, and multi-owner sites with mutation-sensitive tests.

## Outcome

Commits `7633052c17` and `e84f49aa4f` establish the whole-tree join and schema-v3 disposition partition. The live census contains 5,283 sites: 5,282 singly owned, one exact base-class exclusion, zero multi-owner sites, and all 12 re-exported `LedgerStorageError` constructors.

VaultSpec RAG and independent review confirmed the scanner extends the existing census authority without migrating producers or redeclaring error/action authority. Focused verification passes nine tests; Ruff and diff checks pass.

## Notes

- Broader legacy action-census disposition drift belongs to S46 and S47; it does not reduce the authored-message join's coverage.
