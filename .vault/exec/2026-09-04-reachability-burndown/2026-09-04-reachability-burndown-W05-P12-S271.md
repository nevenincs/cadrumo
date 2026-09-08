---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:7818ac6213f18526fd2335b78f084590fa55251170bf3bfe3f7e45b7e720010d'
step_id: 'S271'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the uncomposed repair-remediation decision model/repository and its process-local storage namespace because no product command writes or reads it; remove its synthetic persistence tests and stale registrations while preserving live repair/quarantine session behavior and policy catalog, run focused gates, update cadence, and remeasure exact reachability.

## Scope

- `uncomposed repair-remediation decision persistence slice`
- `process-local namespace`
- `error registrations`
- `self-tests`
- `and policy prose`

## Changes

- `M` `src/cadrumo/application/repair_integrity.py`
- `D` `src/cadrumo/application/tests/test_repair_integrity.py`
- `M` `src/cadrumo/application/tests/test_error_envelope_enrollment.py`
- `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `M` `src/cadrumo/adapters/persistence/storage/namespace_registry.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/_runtime_attached_repositories_support.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_runtime_attached_repositories_part1.py`
- `M` `src/cadrumo/core/errors/registry/_application_part1.py`
- `D` `src/cadrumo/core/tests/test_persisted_version_single_declaration.py`
- `M` `src/cadrumo/locales/ca/application.yml`
- `M` `src/cadrumo/locales/en/application.yml`
- `M` `src/cadrumo/locales/es/application.yml`
- `M` `src/cadrumo/locales/hu/application.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check <focused repair/storage/error files>` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py src/cadrumo/application/tests/test_diagnostics.py -k "repair or quarantine"` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/persistence/storage/tests/test_runtime_attached_repositories_part1.py -k "current_runtime_defaults_refuse_missing_session or runtime_default_surfaces_isolate_active_profile_writes"` -> `fail`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

All 10 live repair-policy, diagnostics, and quarantine tests passed. The runtime-attached selection passed its readiness test and retained an unrelated peer-owned failure because the borrador snapshot fixture omits the now-required registry_snapshot_ref; the deleted repair-decision path is not reached by that failure. Exact unused symbols improved from 273 to 272; 31 unreachable modules and zero orphaned tests remain.
