---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-06'
modified: '2026-06-06'
step_id: 'S460'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W20.P40.S460 - Close stale custody guidance drift

Scope: `src/aeat/adapters/persistence/storage`, `src/aeat/application`, `src/aeat/entrypoints/cli`, `src/aeat/core/errors/registry`, `src/aeat/locales`, `.vault/plan`, `.vault/audit`.

## Description

- Route runtime storage, SQL secure-object expiry, bucket-lock, diagnostics fallback, operator help, profile repair next-action, and registry suggestions away from deprecated profile-switch guidance and onto canonical `aeat config unlock NAME`.
- Route master-key mismatch and recovery-verification copy toward canonical `aeat config recover --recovery-key <WORDS>`.
- Update locale strings through `python -m aeat.locales set`; repair one malformed Hungarian locale scalar that blocked the canonical locale CLI, then continue locale writes through the CLI.
- Add `config lock`, `config unlock`, `config rekey`, `config recover`, `config show-recovery`, and `config verify-recovery` to the backend-owned operator-surface custody contract.
- Update focused tests for bucket error suggestions, session-expiry copy, storage write-policy classification, root-fallback recovery coverage, operator-surface ownership, and recovery-envelope suggestions.
- Add W20.P40.S461 to track the remaining explicit `config profile switch` compatibility decision instead of hiding it inside this guidance-remediation slice.

## Outcome

S460 is closed. Source and locale guidance no longer contain stale `aeat config init`, `aeat config profile switch NAME`, or old recovery-flow phrasing under `src/aeat`. The accepted operator-surface contract now owns the first-class root custody verbs that the CLI mounts.

Validation:

- `uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync ruff check ...` passed for the touched storage, registry, operator-surface, diagnostics, CLI, and focused test files.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/tests/test_bucket_errors.py src/aeat/entrypoints/cli/tests/test_session_lifecycle_roundtrip.py -q` passed.
- `uv run --no-sync pytest -q src/aeat/application/tests/test_storage_write_policy.py src/aeat/entrypoints/cli/tests/test_root_fallback_write_guard.py -q` passed for the unmarked subset.
- `uv run --no-sync pytest -q -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_root_fallback_write_guard.py -k "unlock_remains_recovery_path or leaves_read_and_recovery_paths_open"` passed.
- `uv run --no-sync pytest -q -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py -k "show_does_not_suggest_switch or repair_profile or switch"` passed.
- `uv run --no-sync pytest -q -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_config_profile_surface_inventory.py` passed.
- `uv run --no-sync pytest -q -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/_config/tests/test_config.py -k "profile_switch_missing_profile"` passed.
- `uv run --no-sync pytest -q src/aeat/application/operator_surface/tests/test_contract.py src/aeat/entrypoints/cli/tests/test_cli_workflow_verification.py src/aeat/entrypoints/cli/tests/test_root_help_shape.py -q` passed.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/tests/test_recovery_facade.py -k "recovery_verification_error_round_trips"` passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` passed with the existing PLAN022 monotonic-id warning only.

## Notes

The code-review sidecar identified three issues during the mandatory S460 review: recovery-verification errors suggested `verify-recovery`, custody root verbs were under-declared in the operator-surface contract, and root-fallback coverage still exercised `config profile switch`. All three were fixed before close and persisted in the S460 rolling audit.

The `config profile switch` command remains mounted by current profile-surface inventory tests. S461 now tracks the separate compatibility decision: retire it with migration coverage, or keep it as an explicit compatibility alias hidden from recovery guidance.
