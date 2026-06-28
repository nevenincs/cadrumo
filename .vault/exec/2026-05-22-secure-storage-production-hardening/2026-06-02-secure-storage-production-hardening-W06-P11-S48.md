---
tags: ['#exec', '#secure-storage-production-hardening']
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S48'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W06.P11.S48 Focused Gate Execution Checkpoint

Wave `W06`; Phase `W06.P11`; Step `S48`.

## Description

- Run focused storage and non-live remote-provider gates.
- Run focused config/profile gates.
- Run focused live application and read-only CLI gates.
- Run focused ledger/modelo gates.
- Record any remediations and mandatory review status before closing the step.

## Outcome

The focused S48 behavioral gates are complete and green. One profile/config test still encoded the pre-hardening assumption that a runtime-bound repository's freshness poll should no-op after its bucket session closed. That test now asserts the hardened contract: a repository returned by `isolated_runtime_profile` fails closed with `StorageValidationError`, the translated runtime envelope key `errors.storage.runtime.not_ready`, and a settings-pinned English readiness detail.

Validation passed:

- `uv run --no-sync pytest src/aeat/adapters/persistence/storage src/aeat/adapters/outbound/storage/test_local.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_mirror_adverse_conditions.py -q` - 757 passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/test_session_lifecycle_roundtrip.py src/aeat/application/user_profile -q` - 150 passed.
- `uv run --no-sync pytest src/aeat/application/live/test_borrador_100.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/application/live/test_censo_snapshot.py src/aeat/application/live/test_snapshot_base.py -q` - 52 passed.
- `uv run --no-sync pytest src/aeat/application/live/test_expedientes.py src/aeat/application/live/test_notifications.py src/aeat/application/live/test_verify.py src/aeat/entrypoints/cli/test_live_read_subgroups.py -q` - 60 passed.
- `uv run --no-sync pytest src/aeat/application/live/test_filed_capture_calculation_history.py src/aeat/application/live/test_iva_live_failure_taxonomy.py src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_iva_wallet_privacy_static_guard.py -q` - 32 passed.
- `uv run --no-sync pytest src/aeat/application/ledger src/aeat/domain/modelos src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py src/aeat/entrypoints/cli/test_modelo_casilla_normalisation.py src/aeat/entrypoints/cli/test_modelo_projection.py -q` - 512 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_session_lifecycle_roundtrip.py`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_session_lifecycle_roundtrip.py -q` - 5 passed.
- `git diff --check -- src/aeat/entrypoints/cli/test_session_lifecycle_roundtrip.py`

The combined live command `uv run --no-sync pytest src/aeat/application/live src/aeat/entrypoints/cli/test_live_read_subgroups.py -q` timed out after 184 seconds without a pytest failure summary. Collection reported 144 selected tests; split execution passed all selected slices. The slowest split was the IVA live group at 32 passed in 132.72 seconds, so the monolithic timeout is recorded as gate-runtime pressure rather than a behavioral failure.

Continuation reruns on 2026-06-02 also passed the broader S48 surfaces after registry/profile/config follow-up work:

- `uv run --no-sync pytest src/aeat/adapters/persistence/storage -q` - 725 passed.
- `uv run --no-sync pytest src/aeat/core/test_config_override.py src/aeat/core/test_storage_route_classification.py src/aeat/core/test_bucket_pointer.py src/aeat/core/test_bucket_pointer_io.py src/aeat/core/test_profile.py src/aeat/core/test_profile_catalogue.py src/aeat/core/access_gate src/aeat/application/user_profile -q` - 170 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_202_registry.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py -q` - 27 passed.
- `uv run --no-sync pytest src/aeat/application/modelo -q` - 260 passed.
- `uv run --no-sync pytest src/aeat/domain/modelos -q` - 166 passed.
- `uv run --no-sync pytest src/aeat/adapters/outbound/storage src/aeat/adapters/outbound/google -q` - 163 passed, 7 deselected.
- `uv run --no-sync pytest src/aeat/application/live src/aeat/application/ledger -q` - 320 passed, 1 deselected.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py -q` - 80 passed.
- `uv run --no-sync pytest src/aeat/core/errors/test_registry.py src/aeat/domain/modelos/test_row_models.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py -q` - 101 passed.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage src/aeat/core src/aeat/application/user_profile src/aeat/application/live src/aeat/application/ledger src/aeat/application/modelo src/aeat/domain/modelos src/aeat/adapters/outbound/storage src/aeat/adapters/outbound/google src/aeat/entrypoints/cli/_config src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py` - all checks passed.

## Review Status

Mandatory `vaultspec-code-reviewer` review was requested for S48. The first subagent request failed with the session usage-limit error: "You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at 12:42 PM."

After retry, reviewer `Franklin` completed the mandatory pass with no findings. The reviewer confirmed that the S48 test delta is scoped, uses the real `isolated_runtime_profile` repository, asserts fail-closed `StorageValidationError`, verifies the stable translated key, and avoids fake/stub, env-mutation, tautological-test, and localization-contract drift.

The recorded gate evidence and no-findings review support closing `W06.P11.S48`.
