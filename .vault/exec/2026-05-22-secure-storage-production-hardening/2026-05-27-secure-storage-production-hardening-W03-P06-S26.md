---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-secure-storage-production-hardening-w03-p06-s26-review-audit]]'
---

# `secure-storage-production-hardening` `W03.P06.S26`

Replaced repair namespace marker heuristics with registry ownership metadata.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/application/test_repair_integrity.py`
- Modified: `src/aeat/entrypoints/cli/test_repair_policy_coverage.py`
- Added: `.vault/audit/2026-05-27-secure-storage-production-hardening-W03-P06-S26-review.md`

## Description

`RepairPolicyNamespacePolicy` now carries the registered namespace key, namespace value, owner, sensitivity, schema version, and scope when a policy row represents a secure-object namespace. Secure-object repair surfaces derive those fields from `STORAGE_NAMESPACE_REGISTRY` through `SecureObjectNamespaceDefinition` instead of using the generic `profile_local_secure_object` marker.

`config repair quarantine` and `config repair integrity objects` now expose registry-derived policy rows for every registered secure-object namespace. `config repair reset-state` exposes the concrete `WORKFLOW_STATE_NAMESPACE` registry metadata.

This step does not add discovered namespace completeness enforcement; that remains W03.P06.S27.

## Tests

Passed:

- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_policy_coverage.py`
- `uv run pytest src/aeat/entrypoints/cli/test_repair_policy_coverage.py src/aeat/application/test_repair_integrity.py -q`
- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -q`
- `uv run pytest src/aeat/entrypoints/cli/test_repair_privacy_contract.py src/aeat/application/test_diagnostics.py -q`
- `uv run python -m aeat.locales audit`

Code review found one LOW test coverage follow-up, which was fixed. No HIGH or CRITICAL issues remain.
