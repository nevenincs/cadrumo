---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P22-S91]]'
---

# `secure-storage-production-hardening` Code Review

S91-SELF | INFO | Review opened for `W12.P22.S91`.
Scope: CLI regression coverage for bootstrap availability, explicit profile selection, environment selection, pointer selection, root fallback refusal, explicit database route refusal, profile-switch recovery, and delegation from CLI root to backend runtime/write policy.

S91-001 | PASS | Real-entrypoint behavior is covered without shortcut test doubles.
The reviewed tests run `aeat.entrypoints.cli.main` in subprocesses with isolated settings and assert real exit codes, output text, and absence of fallback database creation. They do not use fakes, stubs, monkeypatching, or duplicated business logic for the guarded behavior.

S91-002 | PASS | Backend policy ownership is guarded.
The reviewed source-boundary assertion rejects `classify_storage_route`, `StorageRouteKind`, and local guarded-route registries in the CLI root while requiring `inspect_storage_write_policy`, preserving the W12 delegation contract.

S91-003 | PASS | Refusal and recovery paths are both represented.
The covered cases include guarded write refusal on root fallback and explicit database routes, bootstrap-safe probes that remain available, and profile-switch recovery that reaches profile resolution without being blocked by the root fallback guard. Deprecated probe names were removed from the regression suite rather than reintroduced.

S91-004 | PASS | Application-owned lifecycle spans are restored.
`src/aeat/entrypoints/cli/_config/__init__.py`, `src/aeat/application/wizard/_commands.py`, and `src/aeat/application/setup/_service.py` no longer contain direct `activate_master_key_provider`, `get_master_key_provider`, `_write_active_profile_pointer`, `_clear_active_profile_pointer`, `capture_active_profile_pointer`, `restore_active_profile_pointer`, or `override_settings(aeat_active_profile...)` spans. Those paths delegate to `profile_create_storage_span`, `profile_storage_session`, `select_profile_with_lifecycle_span`, `delete_profile_with_lifecycle_span`, and `logout_active_profile` in application orchestration.

S91-005 | PASS | Explicit profile selection is covered without weakening command semantics.
Root `--profile` is resolved through manifest discovery to a bucket id before language/session activation. Tests cover pointer default, `AEAT_ACTIVE_PROFILE`, root `--profile` by label and id, command-explicit `profile show NAME`, and write routing through pointer, environment, and root profile override.

S91-006 | PASS | Locale work used the mandated CLI path.
`python -m aeat.locales scaffold` reconciled the new `cli.root.profile_help` key and existing locale drift, and `python -m aeat.locales audit` reports `ok` for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

S91-REVIEWER | INFO | External reviewer unavailable.
The `vaultspec-code-reviewer` agent was invoked for this row but failed before returning a verdict due an external usage limit. Supervisor review continued locally and found no HIGH or CRITICAL issues in the S91 slice.

S91-REREVIEW | PASS | Focused validation passed.
`ruff check` passed for the focused S91/S89-restoration slice. `pytest` reported 58 passing tests across `test_config_custody_profile_lifecycle.py`, `test_root_fallback_write_guard.py`, `test_storage_write_policy.py`, and `test_storage_route_classification.py`. No high or critical findings remain for this row.

S91-REREVIEW-2 | INFO | Delegated review unavailable for widened closeout.
The `vaultspec-code-reviewer` agent was started again for the widened S91 surface but failed before returning findings because the host reported an account usage limit. The supervisor completed this review locally against the same scope and did not treat the failed subagent as a pass.

S91-007 | PASS | Legacy manifest-status repair remains application-owned and fail-closed.
`src/aeat/application/workflow/_profile_health.py:113` reports unreadable active-profile manifests explicitly, `src/aeat/application/workflow/_profile_health.py:236` performs the confirmed repair by loading the encrypted active-profile record and rewriting through the manifest writer, and `src/aeat/application/workflow/test_profile_health.py:161` proves a legacy manifest without `status` moves from `manifest_unreadable` back to `ready`. No CLI-side direct manifest mutation was introduced.

S91-008 | PASS | Profile selection precedence is covered through real CLI processes.
`src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py:142` exercises pointer default selection, `AEAT_ACTIVE_PROFILE` selection, and explicit `--profile` selection using the real CLI harness. The lifecycle ownership guard in the same file also passed, so forbidden CLI custody tokens were not reintroduced.

S91-009 | PASS | Root fallback and explicit-route refusal coverage uses current command surfaces.
`src/aeat/entrypoints/cli/test_root_fallback_write_guard.py:26` lists current bootstrap-safe probes, and `src/aeat/entrypoints/cli/test_root_fallback_write_guard.py:199` verifies they run on root fallback without tripping the profile write guard. Guarded write verbs still assert no fallback database is created and explicit database routes are refused through backend policy.

S91-010 | PASS | Deprecated bootstrap naming and no-untyped-def suppressions were not retained in the touched surface.
`src/aeat/entrypoints/cli/test_workflow_surface.py:140` now names the profile-create flow directly, `src/aeat/entrypoints/cli/_config/__init__.py:2069` through `src/aeat/entrypoints/cli/_config/__init__.py:2135` replace bucket-history `type: ignore[no-untyped-def]` suppressions with concrete annotations, and `src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py:161` removes the archive helper suppression by annotating the SQLAlchemy engine.

S91-REREVIEW-3 | PASS | Final focused validation passed.
`pytest` reported 14 passing profile-custody/bootstrap-repair tests, 40 passing root-fallback/profile-health/archive tests, and 23 passing workflow-surface tests. `ruff check` passed on the S91 touched source and test surface. A targeted scan for `config init`, `config_init`, `init command`, `init_command`, and `type: ignore[no-untyped-def]` across the audited CLI/workflow/wizard/storage surface returned no matches. No HIGH or CRITICAL findings remain for S91.

S91-011 | PASS | Registry specimen gate failure found by workflow-surface validation was resolved without weakening validation.
`src/aeat/_data/registry/aeat/modelos/123/revisions/2019-2023/revision.toml:753` and `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml:942` now mark the Modelo 123 declaration-PDF extraction profiles as `provisional_pending_specimen = true`, matching the registry validator's fail-closed contract when no committed PDF specimen exists. `aeat app registry verify` now reports `Verificado=True`, and `test_workflow_surface.py` passes after a fresh registry verification.
