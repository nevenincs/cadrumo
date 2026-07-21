---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-19'
step_id: '{S##}'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
---

# P07.S41 secret-store DI seam removal (auth-cert-recovery-custody plan)

## Description

## Outcome

## Notes

## Context

Removed the module-global test-double seam from the production secret-store factory, closing `auth-cert-recovery-custody` plan step P07.S41.

**What changed:** `override_secret_store` and its module-global `_override_store` were deleted from `src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py`, along with the re-exports from `blob_store/__init__.py` and the top-level `storage/__init__.py` facade. `materialise_secret` and `export_to_temp_path` already accepted an explicit `store: SecretStore | None = None` parameter, so no new production DI surface was needed there.

The four consuming test files were migrated:
- `blob_store/tests/test_materialisation.py` — the `secret_store` fixture now returns a `SecretStore` directly (no override installation); every `materialise_secret`/`export_to_temp_path` call passes `store=secret_store` explicitly; `test_secret_store_factory_caches_each_explicit_route_independently` dropped its override-specific assertions and kept the per-route-caching assertions.
- `application/auth/tests/test_certificate_secret_backend.py` and `application/auth/tests/test_certificate_sources_check.py` — the `_isolated_secret_store` fixture now returns `get_secret_store()` directly. This works because every test in both files already isolates its settings route (`cadrumo_secret_store_dir`/`cadrumo_blob_store_dir`) via the `isolated_profile_storage_root` fixture and activates a real per-test master-key session via `profile_create_storage_span`/`activate_master_key_provider` — the process-wide override was redundant with that isolation, not load-bearing. Two tests in `test_certificate_sources_check.py` (`test_explicit_settings_second_root_uses_its_own_cached_secret_store`, `test_explicit_settings_same_bucket_id_uses_target_root_and_restores_ambient_session`) called `override_secret_store(None)` only as defensive cleanup with no override ever installed; those calls and their now-pointless `try/finally` wrapping were removed.
- `entrypoints/cli/_config/tests/test_certificate.py` — the `_isolated_secret_store` fixture and its parameter were removed from every test; CLI-level isolation was already fully provided by `isolated_profile_storage_root` + `activate_master_key_provider(get_master_key_provider())` entered inside each test body.

**Note on landing:** this step was executed concurrently by two agents converging on the same seam (a coordinator-dispatched swarm-discovery agent and a directly-tasked executor). The storage-layer files (`_materialisation.py`, both `__init__.py` facades, `test_materialisation.py`) and `test_certificate_secret_backend.py`/`test_certificate.py` were landed by the other agent; this record's author independently reached the same `get_secret_store()`-instead-of-override fix for `test_certificate_sources_check.py` (the one file still open at the time) and verified the full combined result.

**Verification:** `rg override_secret_store` across `src/cadrumo` returns zero matches (only a `.vault/plan/` prose reference to the retired symbol remains, naming it as the thing that was deleted). `ruff check` is clean on all seven touched files. All 65 tests across the four affected test files pass: `pytest src/cadrumo/application/auth/tests/test_certificate_secret_backend.py src/cadrumo/application/auth/tests/test_certificate_sources_check.py src/cadrumo/entrypoints/cli/_config/tests/test_certificate.py src/cadrumo/adapters/persistence/storage/blob_store/tests/test_materialisation.py -q` → `65 passed`. `python -m dev.docs.apidocs scaffold --check` shows no drift attributable to this change (the one pre-existing drift item, `cadrumo.entrypoints.mcp._transport`, is unrelated). `dev/import_hygiene_baseline.json` carries no reference to the removed symbol.

**Deferred:** P07.S42 (AST recurrence gate banning module-global `_override_*` factory state and public `override_*` setters, exempting `core.config.override_settings`) and P07.S43 (facade/apidocs sweep — largely already covered by the verification above, but not yet formalized as its own gate) remain open.
