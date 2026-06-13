---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W01.P004'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-workflow-redesign` `W01.P004`

Closed plan rows:

- `W01.P004.S0019`
- `W01.P004.S0020`
- `W01.P004.S0021`
- `W01.P004.S0022`
- `W01.P004.S0023`
- `W01.P004.S0024`

## Description

W01.P004 added real behavior verification for the apex root and lifecycle contract. Application-level tests now assert the backend-owned root contract accepts only `config` and `app`, rejects retired surfaces with canonical suggestions, and persists bucket-scoped auth events across workflow repository reloads.

CLI-level tests now run a real operator journey through accepted roots only: `config init` creates the active profile, `config profile status` reads it, `config auth configure/status/test` uses backend auth services, `app ledger import` persists a real bank transaction, `app overview status` observes the transaction count, and `app review queue --source-kind ledger_transaction` returns a bucket-scoped row with source kind, affected object id, and period. The same test module proves rejected aliases and retired app domains do not reach services.

## Modified Paths

- `src/aeat/application/test_apex_workflow_verification.py`
- `src/aeat/entrypoints/cli/test_apex_workflow_verification.py`
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

- `uv run --no-sync ruff check src/aeat/application/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_apex_workflow_verification.py`: passed.
- `uv run --no-sync python -m compileall -q src/aeat/application/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_apex_workflow_verification.py`: passed.
- `uv run --no-sync python -m pytest src/aeat/application/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_apex_workflow_verification.py -q`: 4 passed.
- `uv run --no-sync python -m pytest src/aeat/application/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_apex_workflow_verification.py src/aeat/application/operator_surface/test_contract.py src/aeat/application/auth/test_catalogue.py src/aeat/application/auth/test_ensure_session.py src/aeat/application/review/test_adapters.py src/aeat/application/review/test_models.py src/aeat/entrypoints/cli/test_workflow_surface.py::test_root_surface_contains_config_and_app_only src/aeat/entrypoints/cli/test_workflow_surface.py::test_removed_developer_commands_are_not_registered src/aeat/entrypoints/cli/test_workflow_surface.py::test_app_surface_uses_singular_user_domains src/aeat/entrypoints/cli/test_workflow_surface.py::test_app_review_queue_accepts_source_kind_filter src/aeat/entrypoints/cli/test_archive_cli.py src/aeat/entrypoints/cli/test_cli_surface.py tests/import_contract/application/setup/test_cli.py -q`: 73 passed.
