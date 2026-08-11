---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:c955c4c75f0686e48efd766923b8aca430e0e7572acd75c02375de8a95050669'
step_id: 'S32'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate diagnostic remediation records to resolved actions or explicit no-recovery outcomes

## Scope

- `src/cadrumo/application/diagnostics.py`
- `src/cadrumo/application/operator_actions/_catalogue.py`
- `src/cadrumo/application/operator_actions/tests/test_catalogue.py`
- `src/cadrumo/application/tests/test_diagnostics.py`
- `src/cadrumo/entrypoints/cli/_config/_repair_cli.py`
- `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `src/cadrumo/entrypoints/cli/_config/tests/test_config_repair_payloads.py`

## Description

- Replace diagnostic command strings and dead-end prose with application-owned precondition verdicts.
- Register only executable repair actions whose live leaves can recover the failed condition.
- Project verdicts through the canonical CLI resolver and delete legacy fields from every nested repair payload.
- Classify non-executable registry and log-directory conditions with explicit no-recovery outcomes.

## Outcome

Every warning or failure now carries exactly one typed verdict. Authentication readiness resolves to the live login leaf, quarantine and workflow reset carry their required bindings, and a missing log directory no longer points to a read-only command.

The repair result schema rejects `next_action` and `dead_end` at check, finding, and setup boundaries. The focused suite passes 53 tests; Ruff, scoped basedpyright, and diff checks are clean.

## Notes

The repository-wide live action reconciliation remains blocked by unrelated command-tree type drift involving `RevisionId`. Static inspection and direct catalogue tests establish the corrected targets and bindings for this Step.
