---
tags:
  - '#exec'
  - '#google-client-provisioning'
date: '2026-10-06'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:a229151237010b8168724bc94b29114a7ff723c814da9b168f56f8558cde4bd2'
related:
  - "[[2026-10-06-google-client-provisioning-plan]]"
---

# `google-client-provisioning` ledger

## Changes

- `S01` `A` `src/cadrumo/core/config_google.py`
- `S01` `A` `src/cadrumo/core/config_google_client.py`
- `S01` `M` `src/cadrumo/core/config.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/installation_client.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/records.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/oauth_flow.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/sign_in_state.py`
- `S01` `M` `src/cadrumo/adapters/outbound/storage/factory.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/tests/installation_client_support.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/tests/test_installation_client.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/tests/test_records.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/tests/test_oauth_flow.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_google_configuration_native.py`
- `S01` `M` `src/cadrumo/conftest.py`
- `S01` `M` `env/.env.example`
- `S01` `M` `docs/reference/environment-overrides.md`
- `S01` `verify:` `focused OAuth settings and environment-reference pytest suite (129 combined tests)` -> `pass`
- `S01` `verify:` `scoped Ruff format and ty` -> `pass`
- `S02` `M` `dev/env/_dotenv.py`
- `S02` `M` `dev/env/tests/test_dotenv.py`
- `S02` `M` `packaging/authority/hatch_build.py`
- `S02` `M` `dev/packaging/native/product.py`
- `S02` `M` `dev/packaging/native/cmake_build.py`
- `S02` `M` `native/cmake/Packaging.cmake`
- `S02` `M` `dev/packaging/python_cohort.py`
- `S02` `M` `dev/packaging/release_cohort.py`
- `S02` `M` `dev/packaging/tests/test_authority_build_hook.py`
- `S02` `M` `.importlinter`
- `S02` `A` `dev/conftest.py`
- `S02` `A` `dev/packaging/google_oauth.py`
- `S02` `A` `dev/packaging/tests/test_google_oauth_provisioning.py`
- `S02` `verify:` `development environment and provisioning pytest (21 tests)` -> `pass`
- `S02` `verify:` `packaging cohort and cache scoped pytest (56 applicable tests)` -> `pass`
- `S02` `verify:` `scoped Ruff format ty and closed-dev-classification` -> `pass`
- `S02` `verify:` `cmake preset windows-x64 docs enabled` -> `pass`
- `S02` `verify:` `cmake build native_contract and rust_application Debug` -> `pass`
- `S03` `M` `.github/workflows/release.yml`
- `S03` `M` `.gitignore`
- `S03` `M` `.vault/adr/2026-10-04-google-app-identity-adr.md`
- `S03` `A` `.vault/audit/2026-10-06-google-client-provisioning-audit.md`
- `S03` `verify:` `just check-workflows` -> `pass`
- `S03` `verify:` `private configuration and reachable history assertions` -> `pass`
- `S03` `verify:` `independent integrated review` -> `pass`
- `S03` `verify:` `repository-wide lint format type and import checks` -> `fail`

## Notes

- `S01` Existing unrelated worktree changes are preserved; task-only staging uses pre-task snapshots.
- `S02` Two pre-existing packaging failures (authority currency and interpreter patch pin) excluded from applicable packaging run.
- `S02` Task checkpoint includes the CMake always-run product target needed to evaluate credential changes; other pre-existing native edits remain in working tree.
- `S03` Whole-repository failures are pre-existing outside task scope; task-owned issues were corrected and scoped checks passed.
- `S03` Ignored main/env/.env and tui/env/.env provisioned; GitHub repository secret set and name read back.
- `S03` Restricted rewrite removed the credential blob from all reachable refs/reflogs, preserving unrelated trees and remote ancestry. No remote push and no aggressive physical object pruning.
- `S03` ADR checkpoint isolates this task amendment; pre-existing ADR amendments remain in the working tree. No live OAuth or full installer validation performed.
