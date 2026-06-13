---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P23.S93` Workflow Run Hardening Slice

Hardened the workflow-run runtime-profile anti-tautology test by replacing broad exception capture with a concrete validation-boundary assertion.

## Changes

- Replaced the workflow-run aborted-reason drift sentinel's broad `except Exception` / boolean flag with `pytest.raises(ValidationError)`.
- Kept the mutation path on the runtime repository public API, preserving the same encrypted-object boundary the production load path reads.
- Removed stale docstring wording that referred to bypassing `SecureObjectRow` / `session_scope`.

## Validation

- `uv run --no-sync pytest src/aeat/application/workflow/test_run_persistence_roundtrip.py -q` - 2 passed.
- `uv run --no-sync ruff check src/aeat/application/workflow/test_run_persistence_roundtrip.py` - passed.
- `rg -n "except Exception|AEAT_DATABASE_URL|aeat_database_url|create_engine_from_settings|SecureObjectRepository\(|Base\.metadata|SecureObjectRow|session_scope\(|EphemeralMasterKeyProvider|monkeypatch|pragma: no cover|noqa|type: ignore\[no-untyped-def\]" ...workflow run slice...` - no matches.
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` - still blocked by duplicate W07/W08 canonical identifiers around `P14` and `S56` through `S61`, unrelated to this source slice.

## Review

The `vaultspec-code-reviewer` review found no issues. The reviewer confirmed that the concrete `ValidationError` assertion is correct for the `Envelope[WorkflowResult].model_validate_json` reconstruction path and that no broad exception swallowing, pragma/noqa masking, monkeypatch/database-url setup, or stale direct-ORM wording remains.

S93 remains open because the plan row covers the broader `src/aeat` migration. S94 and S95 still need guard coverage and approved explicit-route inventory.
