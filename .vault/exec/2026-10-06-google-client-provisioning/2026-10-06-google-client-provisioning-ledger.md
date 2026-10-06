---
tags:
  - '#exec'
  - '#google-client-provisioning'
date: '2026-10-06'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:67e3aa4199bb3d18aec74d87f135187b5fd9acdaf561c382be38f44d17464f58'
related:
  - "[[2026-10-06-google-client-provisioning-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `google-client-provisioning` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

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
