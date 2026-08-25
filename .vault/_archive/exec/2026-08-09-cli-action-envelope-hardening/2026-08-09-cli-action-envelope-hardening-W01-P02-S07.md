---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:2dd56bfc2730025aea98686e9e347135104412c626441b8f5ef2948b444decc2'
step_id: 'S07'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Prove identity joins for callbacks, aliases, exclusions, and policy-filtered MCP leaves

## Scope

- `src/cadrumo/application/operator_surface/tests/test_contract.py`
- `src/cadrumo/entrypoints/schema_surface.py`
- `src/cadrumo/application/operator_surface/_models.py`
- `src/cadrumo/application/operator_surface/_contract.py`

## Description

- Materialise the production Typer/Click root and independently traverse every terminal command path and each `invoke_without_command` callback path.
- Declare callback-owned schemas, descendant callback result reuse, and help-only callback exclusion together in the entrypoint schema-surface authority.
- Reconcile raw paths bidirectionally with result schemas, S05 input schemas, root landing exclusions, mounted families, storage profile policy, and observed MCP descriptors.
- Derive the expected MCP descriptor identities from raw terminal paths plus declared callback-owned schemas, excluding only root landing keys and never calling the MCP exposure filter for expectation.
- Add the `PROVISIONING` mounted family and prove its domain, owner, mutability, operator wording, child membership, and exact live Click declaration order.
- Classify the cross-layer proof as `integration` while retaining `unit` as the sole execution marker for application-only tests.

## Outcome

The live operator identity proof now starts from the materialised CLI rather than from schema registrations. A missing schema, orphan registration, unrecorded callback, mistaken MCP filter, profile-policy mismatch, or drifted provisioning command order produces a named reconciliation failure. Review remediation also corrected the canonical operator question to explicitly state provisioning readiness.

## Verification

`uv run --no-sync pytest -n0 -m integration src/cadrumo/application/operator_surface/tests/test_contract.py::test_live_operator_surface_reconciles_raw_click_paths_callbacks_and_mcp_policy_by_identity`

`1 passed in 5.96s`

`uv run --no-sync pytest -n0 -m "unit or integration" src/cadrumo/application/operator_surface/tests/test_manifest_reconciliation.py src/cadrumo/application/operator_surface/tests/test_contract.py`

`31 passed in 25.11s`

`uv run --no-sync ruff check src/cadrumo/application/operator_surface/tests/test_contract.py src/cadrumo/application/operator_surface/_contract.py src/cadrumo/application/operator_surface/_models.py src/cadrumo/entrypoints/schema_surface.py`

`All checks passed!`

`uv run --no-sync basedpyright src/cadrumo/application/operator_surface/tests/test_contract.py src/cadrumo/application/operator_surface/_contract.py src/cadrumo/application/operator_surface/_models.py src/cadrumo/entrypoints/schema_surface.py`

`0 errors, 0 warnings, 0 notes`

`git diff --check -- src/cadrumo/application/operator_surface/tests/test_contract.py src/cadrumo/application/operator_surface/_contract.py src/cadrumo/application/operator_surface/_models.py src/cadrumo/entrypoints/schema_surface.py`

`Exit code: 0`

## Notes

The first integration run correctly failed because the new provisioning operator question named readiness but not provisioning. The production wording was corrected before the passing rerun. No staging, commit, lock-file, or unrelated worktree mutation was performed.
