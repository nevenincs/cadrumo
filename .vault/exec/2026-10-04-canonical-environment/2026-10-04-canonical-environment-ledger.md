---
tags:
  - '#exec'
  - '#canonical-environment'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:2feb9c8cc00405e38b7cb8a8e32f2719527200ad3866b2f0b1ad36274ae157d0'
related:
  - "[[2026-10-04-canonical-environment-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `canonical-environment` ledger

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

- `S01` `M` `src/cadrumo/core/storage_environment.py`
- `S01` `M` `src/cadrumo/core/storage_taxonomy.py`
- `S01` `M` `src/cadrumo/core/storage_taxonomy_locations.py`
- `S01` `M` `src/cadrumo/core/config_state_root.py`
- `S01` `M` `src/cadrumo/core/_config_runtime.py`
- `S01` `M` `src/cadrumo/core/config.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/main.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/profile_worker.py`
- `S01` `M` `src/cadrumo/core/tests/test_storage_environment.py`
- `S01` `A` `src/cadrumo/core/tests/test_storage_root_vectors.py`
- `S01` `M` `src/cadrumo/core/tests/test_config_state_root.py`
- `S01` `M` `src/cadrumo/core/tests/test_config.py`
- `S01` `M` `src/cadrumo/core/tests/test_output_dir_state_root.py`
- `S01` `M` `src/cadrumo/core/tests/test_storage_fingerprint_participation_gate.py`
- `S01` `M` `src/cadrumo/core/tests/test_settings_lifecycle_gate.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/tests/test_worker_storage_environment.py`
- `S01` `M` `env/.env.example`
- `S01` `M` `docs/reference/environment-overrides.md`
- `S01` `verify:` `uv run --no-sync python -m pytest src/cadrumo/core/tests src/cadrumo/tests/test_storage_provenance_gate.py (storage, settings, taxonomy, vector and installed-layout tests)` -> `pass`
- `S01` `verify:` `uv run --no-sync python -m pytest kdf supervision, profile worker, worker storage environment, CLI metadata contract, dev/docs env reference, dev/packaging native contract` -> `pass`
- `S01` `verify:` `uv run --no-sync python -m dev.quality.types (ty, pyrefly, basedpyright; no diagnostic in touched files)` -> `pass`
- `S01` `verify:` `dev.quality.import_gate (15 of 15 contracts kept, no finding in touched files)` -> `pass`
- `S01` `verify:` `ruff check and ruff format --check on touched files` -> `pass`
- `S01` `verify:` `WSL Ubuntu python3 installed-copy probe: XDG and HOME defaults, cwd independence, root mode 0o700` -> `pass`
- `S01` `by:` `implementation-engineer-high`
- `S01` `M` `src/cadrumo/core/storage_materialization.py`
- `S01` `M` `src/cadrumo/core/tests/test_ensure_storage_tree.py`
- `S01` `verify:` `WSL Ubuntu venv pytest test_ensure_storage_tree.py and test_storage_root_vectors.py (POSIX root 0o700, installed layout, undeclared platform)` -> `pass`
- `S01` `verify:` `uv run --no-sync python -m pytest storage, settings, ensure-tree, storage-management, worker, KDF and CLI metadata tests plus structural storage gates` -> `pass`

## Notes

- `S01` Allowlist narrowing deferred to S02 by orchestrator decision: `Settings.storage_env_var_names()` still returns product plus development tool names, because dev/packaging/native/generate.py requires `CADRUMO_TOOL_CACHE_DIR` in it; `development_tool_env_var_names()` and `product_env_var_names()` were added as additive accessors.
- `S01` `child_environment` passes host-inherited pins `CADRUMO_AUTHORITY_ROOT` and, on Windows, `XDG_CACHE_HOME` in both profiles, because the packaged pywin32 patch reads `XDG_CACHE_HOME` until S02 and S03 declare a successor (orchestrator-approved).
- `S01` Outside the S01 file list: the profile worker's owning test, env/.env.example, and the regenerated docs/reference/environment-overrides.md were updated because the new Settings field and the root pin required them.
- `S01` Root creation at mode 0o700 is wired into `prepare_temporary_directory` and `child_environment,` but not yet into `ensure_storage_tree` `(core/storage_materialization.py` is outside the S01 file list).
- `S01` `test_redaction_recorded_sequence_output::test_no_recorded_operator_line_is_rewritten_unless_it_carries_an_identity` exceeds the 300 s pytest timeout under current machine load. It is unrelated to this Step: it touches no storage or Settings code, and it passed at 218 s earlier in this session.
- `S01` Orchestrator rulings applied: outside-list files approved; `ensure_storage_tree` creates the root through `ensure_storage_root` with `STORAGE_ROOT.posix_directory_mode` `(STORAGE_ROOT_MODE` now reads the declaration); development mode resolves on any sys.platform and only the installed default refuses an undeclared platform.
