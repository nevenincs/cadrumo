---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S91'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-w12-p22-s91-review-audit]]'
---



# `secure-storage-production-hardening` `W12.P22.S91`

Closed the CLI regression-test row for backend-owned runtime/write policy refusal, explicit profile selection, and the profile bootstrap regressions found while exercising that row.

## Evidence

- Existing regression coverage exercises the real CLI entrypoint in subprocesses rather than monkeypatching command internals.
- Guarded profile-bound write verbs refuse root fallback databases before creating fallback storage and refuse explicit database routes through backend runtime readiness policy.
- Bootstrap-safe probes and profile-switch recovery paths remain available on a fresh root, using current command surfaces rather than removed or stale verbs.
- Profile custody coverage now exercises file-backed profile creation, switch reopening, explicit environment selection, pointer selection, and explicit `--profile` precedence.
- Root `--profile` resolves labels or bucket ids through manifest discovery before language/session activation.
- CLI config, wizard, and setup create/select/delete/logout flows delegate pointer and master-key custody spans to application user-profile orchestration.
- Application workflow health now reports legacy manifests missing lifecycle status as `manifest_unreadable` and repairs that torn state by backfilling status from the encrypted profile record through the atomic manifest writer.
- CLI bucket-history helper suppressions were replaced with concrete annotations, and stale `config init` wording was removed from the touched CLI regression surface.
- Compatibility fixes kept the runtime path importable while the S91 tests ran: calculation registry snapshot export, storage runtime export, missing error-registry rows, and manifest key-schedule / idle-lock fields.
- Locale reconciliation was performed through `python -m aeat.locales scaffold`, and the locale audit now reports all locale catalogues as `ok`.
- Workflow-surface validation exposed missing provisional specimen markers on the Modelo 123 declaration-PDF extraction profiles; both registry revisions now explicitly acknowledge the missing PDF specimen instead of allowing registry validation to fail during deadline computation.

## Validation

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py src/aeat/application/test_storage_write_policy.py src/aeat/core/test_storage_route_classification.py -q` - 58 passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py -q` - 14 passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_root_fallback_write_guard.py src/aeat/application/workflow/test_profile_health.py src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py -q` - 40 passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_workflow_surface.py -q` - 23 passed.
- `uv run --no-sync aeat app registry verify` - passed with `Verificado=True`.
- `uv run --no-sync ruff check` on the S91/S89-restoration touched source and test surface passed.
- `uv run --no-sync python -m aeat.locales audit` - passed.
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` - passed.
- Hygiene scan for `config init`, `config_init`, `init command`, `init_command`, and `type: ignore[no-untyped-def]` across the audited CLI/workflow/wizard/storage surface returned no matches.

## Review

The delegated reviewer agent was requested but failed before returning findings because the runtime reported an account usage limit. A local code-review pass was persisted in the linked audit. No high or critical S91 issues were found.
