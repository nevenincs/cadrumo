---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---



# `secure-storage-production-hardening` audit: `settings-backed route handling`

## Scope

Audited secure-storage and storage-adjacent tests for centralized `Settings` usage, naked environment access, and direct database-route shortcuts.

## Good Patterns

- `src/aeat/core/config.py` centralizes `StorageRouteKind`, `StorageRouteClassification`, and `classify_storage_route(...)`.
- `src/aeat/adapters/persistence/storage/sql/engine.py` defaults through `load_settings()` and resolves database routes from centralized settings.
- `src/aeat/tests/secure_sql.py` uses `override_settings(...)` and `dispose_engine(...)` for isolated secure SQL test setup.
- Recent projection and profile-runtime tests use `override_settings(...)` instead of mutating process environment directly.

## Findings

- Medium: `src/aeat/adapters/persistence/storage/runtime.py` synthesizes bucket settings by constructing `Settings(...)` and editing pydantic field-set internals so `aeat_database_url` is not treated as explicit. This preserved current behavior, but it is a convention smell: route synthesis should live behind a central settings helper rather than manipulating model internals in storage runtime code.
- Medium: `src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py` and `src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py` still bind `AEAT_DATABASE_URL` through `monkeypatch.setenv(...)` for secure-storage tests. New tests should use settings-backed fixtures unless they are explicitly testing environment parsing.
- Medium: `src/aeat/application/test_diagnostics.py` still contains manual `os.environ[...]` and restore logic around `AEAT_DATABASE_URL` for secure-storage repair tests. This should be converted to `override_settings(...)` or a central secure SQL fixture.
- Low/Medium: `src/aeat/application/review/test_adapters.py` and `src/aeat/application/review/test_aggregator.py` directly mutate `os.environ["AEAT_DATABASE_URL"]` in autouse fixtures. Those paths should use centralized settings helpers to avoid leaking route state across tests.

## Disposition

- `W11.P19.S74` owns replacing naked environment mutation and ad hoc route synthesis with centralized settings helpers.
- `W11.P19.S77` should add guard coverage that distinguishes tests of environment parsing from ordinary storage-route setup.

## Repairs

- `W11.P19.S74` moved named profile-bucket settings derivation into `src/aeat/core/config.py` via `settings_for_active_profile_bucket(...)`.
- `W11.P19.S74` updated `src/aeat/adapters/persistence/storage/runtime.py` to consume the central helper instead of constructing `Settings(...)` and mutating pydantic field-set internals locally.
- `W11.P19.S74` preserved explicit-route fail-closed behavior: the central helper refuses source settings that explicitly set `aeat_database_url` rather than silently converting them into bucket routes.
- `W11.P19.S74` added route-classification coverage proving the helper derives an active bucket route without marking `aeat_database_url` explicit and rejects blank bucket ids or explicit database URLs.

## Validation

The audit used targeted scans for `os.environ`, `os.getenv`, `monkeypatch.setenv`, `AEAT_DATABASE_URL`, `Settings(...)`, `load_settings()`, and `override_settings(...)`, then inspected representative route and secure SQL setup code.

Follow-up validation for the central route helper included focused ruff checks plus real `Settings`, storage runtime, and config tests.
