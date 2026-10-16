---
tags:
  - '#exec'
  - '#native-build-confinement'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:1e0b7222c7d241c90ca29cf2941f4c25eecce88966ad9e5816858f1ba9b393c4'
related:
  - "[[2026-10-16-native-build-confinement-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `native-build-confinement` ledger

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

- `S02` `M` `dev/packaging/native/verification_paths.py`
- `S02` `M` `dev/packaging/native/verify.py`
- `S02` `M` `dev/packaging/native/environment_facts.py`
- `S02` `M` `dev/packaging/native/environment_conformance.py`
- `S02` `M` `dev/packaging/native/launch_guard_check.py`
- `S02` `M` `dev/packaging/native/package_launch_smoke.py`
- `S02` `M` `dev/packaging/native/platforms/windows_verify.py`
- `S02` `M` `dev/packaging/native/platforms/windows_trace_analysis.py`
- `S02` `M` `dev/packaging/native/platforms/windows_trace.ps1`
- `S02` `M` `dev/packaging/native/agent.py`
- `S02` `M` `dev/packaging/native/artifact_verify.py`
- `S02` `M` `dev/packaging/native/assemble.py`
- `S02` `M` `dev/packaging/native/authority_build.py`
- `S02` `M` `dev/packaging/native/cached_command.py`
- `S02` `M` `dev/packaging/native/cleanup.py`
- `S02` `M` `dev/packaging/native/cmake_build.py`
- `S02` `M` `dev/packaging/native/distribution_prepare.py`
- `S02` `M` `dev/packaging/native/docs_build.py`
- `S02` `M` `dev/packaging/native/docs_stage.py`
- `S02` `M` `dev/packaging/native/installation.py`
- `S02` `M` `dev/packaging/native/linux_packages.py`
- `S02` `M` `dev/packaging/native/process_quiescence.py`
- `S02` `M` `dev/packaging/native/trace_analysis.py`
- `S02` `M` `dev/packaging/native/update_agent.py`
- `S02` `M` `dev/packaging/native/update_images.py`
- `S02` `M` `dev/packaging/native/windows_msi.py`
- `S02` `M` `dev/packaging/native/windows_msi_build.py`
- `S02` `M` `dev/packaging/native/identity.py`
- `S02` `M` `dev/packaging/native/generate.py`
- `S02` `M` `dev/packaging/native/metadata.py`
- `S02` `M` `dev/packaging/native/product.py`
- `S02` `M` `dev/packaging/native/provision.py`
- `S02` `M` `dev/packaging/native/build_toolchain.py`
- `S02` `M` `dev/packaging/native/linux_desktop_runtime.py`
- `S02` `M` `dev/packaging/native/tests/test_cached_command.py`
- `S02` `M` `dev/packaging/native/tests/test_cleanup.py`
- `S02` `M` `dev/packaging/native/tests/test_authority_build_fingerprints.py`
- `S02` `M` `dev/packaging/native/tests/test_docs_build_environment.py`
- `S02` `M` `dev/packaging/native/tests/test_docs_input_publication.py`
- `S02` `M` `dev/packaging/native/tests/test_docs_input_identity.py`
- `S02` `M` `native/cmake/LaunchGuard.cmake`
- `S02` `M` `native/cmake/Packaging.cmake`
- `S02` `M` `native/cmake/Contract.cmake`
- `S02` `M` `native/cmake/Manager.cmake`
- `S02` `M` `native/cmake/ReleaseVerification.cmake`
- `S02` `M` `native/cmake/PackageInputs.cmake`
- `S02` `M` `native/cmake/Docs.cmake`
- `S02` `M` `native/cmake/platforms/Posix.cmake`
- `S02` `M` `native/cmake/platforms/Windows.cmake`
- `S02` `M` `native/cmake/Authority.cmake`
- `S02` `M` `native/cmake/Agent.cmake`
- `S02` `M` `native/cmake/distribution/CMakeLists.txt`
- `S02` `M` `dev/packaging/tests/test_native_storage_environment_contract.py`
- `S02` `M` `CMakeLists.txt`
- `S02` `M` `native/CONTRACT.md`
- `S02` `A` `dev/packaging/native/build_directory.py`
- `S02` `A` `dev/packaging/native/tests/test_build_directory_admission.py`
- `S02` `A` `dev/packaging/native/tests/cmake_build_fixture.py`
- `S02` `A` `dev/packaging/native/tests/test_generator_output_boundaries.py`
- `S02` `M` `.vaultspec/skills/cadrumo-start/references/build-cmake-and-packaging.md`
- `S02` `M` `.agents/skills/cadrumo-start/references/build-cmake-and-packaging.md`
- `S02` `M` `.vaultspec/skills/cadrumo-start/references/build-python-packaging-and-release.md`
- `S02` `M` `.agents/skills/cadrumo-start/references/build-python-packaging-and-release.md`
- `S02` `M` `.vaultspec/skills/cadrumo-start/references/build-desktop-frontend.md`
- `S02` `M` `.agents/skills/cadrumo-start/references/build-desktop-frontend.md`
- `S02` `verify:` `focused writer-cache-cleanup-authority-docs pytest (67 tests)` -> `pass`
- `S02` `verify:` `direct-generator admission pytest after assembly correction (8 tests)` -> `pass`
- `S02` `verify:` `ty changed native entry modules (22 files)` -> `pass`
- `S02` `verify:` `ruff check dev/packaging/native` -> `pass`
- `S02` `verify:` `broad native pytest (1028 passed, 7 skipped, 5 failed)` -> `fail`
- `S02` `verify:` `configured repository type check (65 diagnostics)` -> `fail`
- `S02` `verify:` `import-linter (24 kept, 1 broken)` -> `fail`
- `S02` `verify:` `native format check (2 concurrent files unformatted)` -> `fail`
- `S02` `A` `.vault/reference/2026-10-16-native-build-confinement-writer-census-reference.md`
- `S02` `A` `.vault/audit/2026-10-16-native-build-confinement-audit.md`
- `S01` `M` `packaging/authority/hatch_build.py`
- `S01` `M` `dev/packaging/tests/test_authority_build_hook.py`
- `S01` `M` `pyproject.toml`
- `S01` `verify:` `authority build hook pytest (15 tests)` -> `pass`
- `S01` `verify:` `ruff check and format authority hook and tests` -> `pass`
- `S02` `M` `native/desktop/scripts/frontend-install.mjs`
- `S02` `M` `native/desktop/tests/frontend-install.test.mjs`
- `S02` `M` `native/desktop/CMakeLists.txt`
- `S02` `M` `native/cmake/BinaryDirectory.cmake`
- `S02` `M` `native/desktop/scripts/build-paths.mjs`
- `S02` `M` `native/desktop/tests/build-paths.test.mjs`
- `S02` `M` `native/desktop/scripts/tauri.mjs`
- `S02` `M` `native/desktop/tests/run-backend.ps1`
- `S02` `M` `native/desktop/tests/run-packaged.ps1`
- `S02` `M` `native/cmake/BuildPaths.cmake`
- `S02` `M` `CMakePresets.json`
- `S02` `M` `dev/packaging/native/tests/test_binary_directory.py`
- `S02` `A` `native/cmake/CTestEnvironment.cmake`
- `S02` `A` `dev/packaging/native/tests/test_ctest_environment.py`
- `S02` `verify:` `Node frontend prerequisites (12 tests)` -> `pass`
- `S02` `verify:` `Node build-path admission (6 tests)` -> `pass`
- `S02` `verify:` `CMake binary/child admission pytest (19 tests)` -> `pass`
- `S02` `verify:` `nested CTest environment behavioral pytest (1 test)` -> `pass`
- `S02` `verify:` `PowerShell parser backend and packaged wrappers` -> `pass`
- `S02` `verify:` `Ruff changed CMake admission tests` -> `pass`
- `S02` `verify:` `combined current native ownership/cache/cleanup/CMake/CTest/authority/docs pytest (88 tests)` -> `pass`
- `S02` `verify:` `native Ruff check and authority-hook style checks` -> `pass`
- `S02` `verify:` `native format excluding 2 independently edited files (155 files)` -> `pass`
- `S01` `M` `justfile`
- `S01` `M` `env/.env.example`
- `S01` `M` `.github/actions/setup/action.yml`
- `S01` `M` `.github/workflows/docs-health.yml`
- `S01` `M` `dev/docs/build_paths.py`
- `S01` `M` `dev/docs/build.py`
- `S01` `M` `dev/docs/tests/test_docs_build.py`
- `S01` `M` `src/cadrumo/core/tests/test_storage_environment.py`
- `S01` `M` `dev/tests/test_storage_bootstrap_parity.py`
- `S01` `M` `dev/tests/test_native_build_recipes.py`
- `S01` `M` `conftest.py`
- `S01` `M` `src/cadrumo/conftest.py`
- `S01` `M` `dev/test_runs/command.py`
- `S01` `M` `dev/test_runs/logging.py`
- `S01` `M` `dev/test_runs/tests/test_command.py`
- `S01` `M` `dev/test_runs/tests/test_logging.py`
- `S01` `verify:` `tool bootstrap native recipes and storage parity pytest (34 integration tests)` -> `pass`
- `S01` `verify:` `core tool storage pytest (20 tests)` -> `pass`
- `S01` `verify:` `ambient XDG/test-run subprocess regressions (2 tests)` -> `pass`
- `S01` `verify:` `Ruff test-run environment files` -> `pass`
- `S01` `A` `dev/packaging/build_storage.py`
- `S01` `A` `dev/packaging/tests/test_build_storage.py`
- `S01` `verify:` `build storage context and CLI pytest (5 tests)` -> `pass`
- `S01` `verify:` `Ruff check and format new build storage files` -> `pass`
- `S01` `verify:` `ty new build storage files` -> `pass`
- `S02` `verify:` `final Ruff native and authority/build-storage scope` -> `pass`
- `S02` `verify:` `final native format check (157 files)` -> `pass`
- `S02` `verify:` `fresh configured repository types with build-owned state (10 diagnostics)` -> `fail`
- `S02` `verify:` `ty changed packaging cohort/release/storage/cleanup modules (6 files)` -> `pass`
- `S01` `M` `.github/workflows/release.yml`
- `S01` `M` `RELEASING.md`
- `S01` `M` `dev/env/clean.py`
- `S01` `M` `dev/env/tests/test_clean.py`
- `S01` `M` `dev/packaging/build_scratch_reclaim.py`
- `S01` `M` `dev/packaging/campaign.py`
- `S01` `M` `dev/packaging/python_cohort.py`
- `S01` `M` `dev/packaging/release_cohort.py`
- `S01` `M` `dev/packaging/tests/test_build_scratch_reclaim.py`
- `S01` `M` `dev/packaging/tests/test_campaign.py`
- `S01` `M` `dev/packaging/tests/test_cohort_source_identity.py`
- `S01` `M` `dev/packaging/tests/test_release_cohort.py`
- `S01` `M` `dev/release/tests/test_justfile_release_guidance.py`
- `S01` `M` `src/cadrumo/core/storage_environment.py`
- `S01` `verify:` `final packaging storage/scratch/cohort/release/campaign/recipes focused pytest (144 tests)` -> `pass`
- `S01` `verify:` `final scoped Ruff and format packaging release changes` -> `pass`
- `S01` `verify:` `final scoped ty packaging release changes` -> `pass`
- `S01` `verify:` `independent integrated Luna review of build storage/cohort/release/campaign` -> `pass`
- `S01` `verify:` `docs test_docs_build.py collection (DeferredTarget module validation)` -> `fail`
- `S02` `M` `.github/workflows/release.yml`
- `S02` `M` `dev/release/readiness.py`
- `S02` `M` `dev/release/tests/test_distribution_readiness.py`
- `S02` `M` `dev/packaging/tests/test_preflight_recipe_selection.py`
- `S02` `M` `justfile`
- `S02` `M` `dev/packaging/native/tests/test_builder_identity.py`
- `S02` `M` `dev/packaging/native/tests/test_cmake_installer_flow.py`
- `S02` `M` `dev/tests/test_native_build_recipes.py`
- `S02` `verify:` `independent review follow-up: focused pytest cleanup/builder_identity/installer_flow/preflight/authority/readiness` -> `pass`
- `S02` `verify:` `node --test frontend-install and frontend-clean (16 tests)` -> `pass`
- `S02` `verify:` `ruff check, ruff format --check, ty on touched Python` -> `pass`
- `S02` `verify:` `uv run python -m dev.quality.types --count (0 diagnostics)` -> `pass`
- `S02` `verify:` `docs test_docs_build.py collect-only (66 tests, 0 errors)` -> `pass`
- `S02` `verify:` `pytest dev/packaging dev/release dev/env dev/tests -n 6 (2630 passed, 26 failed)` -> `fail`

## Notes

- `S02` Shared working tree is concurrently edited by another session; changes remain uncommitted and required global gates unresolved. S02 remains open. Desktop and CMake final boundary evidence will be appended after agent completion.
- `S02` Direct pytest commands retain the development test-run storage policy unless the operator supplies build-owned storage/log/scratch overrides; CMake-controlled test steps are being explicitly bound to build outputs. No native binary rebuild or OS filesystem trace was run.
- `S01` Ordinary wheel/sdist builds now refuse missing authority; explicit editable environment setup retains publication behavior.
- `S02` Desktop PowerShell wrapper was not run end to end: existing configured desktop manifest is stale and requires reconfiguration. No full native bundle build. Admission is not a sandbox against concurrent post-check filesystem replacement.
- `S02` Combined 88-test run 20261016T080115.509722Z-pytest-33064-589d4835 used build/windows-x64/testing/build-confinement-final for its own storage/logs/scratch. Later docs alias correction is covered by this run.
- `S01` Initial S01 environment work passed targeted checks; related release path migration and accidental replacement-script text recovery are still under verification. Required repository gates remain unresolved and no commit has been created in the shared worktree.
- `S01` Application state/scratch/cache controls are bound to admitted build work and restored after use. UV, XDG, tool caches and machine homes remain untouched. CLI propagates child status and refuses external work before writes.
- `S02` The fresh type gate has 10 diagnostics across runtime/CLI/docs/settings files. `storage_environment.py:586` is authority settings Pydantic `model_fields` inference, outside removed tool-location declarations; scoped checks do not reproduce that global inference diagnostic. Initial quality invocation needed explicit repo/src PYTHONPATH; rerun used that standard source import path and `build_storage` for diagnostics/scratch.
- `S01` The original 222-case run passed218 and failed4 expectations/setup; affected groups were corrected and reran passing, followed by final144-case focused run including latest guards and command prefixes. Docs module collection remains blocked by unrelated current command-graph validation. Replacement-loop corruption was repaired from read-only baseline; independent review of all5 touched files and diff whitespace checks passed. Orphan release source snapshots are retained and reported for manual review, including under clean-apply. Global gates unresolved; Steps remain open and changes uncommitted by this session.
- `S02` 26 wide-run failures traced to a concurrent native/application/Cargo.toml test-target edit by another session that staled the Linux desktop dependency hash; that session refreshed `linux_desktop_runtime.py` and reported 47 passed. `test_process_quiescence` and one installer-flow run failed only under -n 6 load and pass alone.
- `S02` Desktop node tests build-paths/configuration/development-server/headless/startup require `CADRUMO_CMAKE_BINARY_DIR` from a configured CMake target and fail when run bare.
- `S02` Release-workflow tap checkouts and acquisition/readiness evidence under var/ are release scratch, not native build outputs, and remain there.
