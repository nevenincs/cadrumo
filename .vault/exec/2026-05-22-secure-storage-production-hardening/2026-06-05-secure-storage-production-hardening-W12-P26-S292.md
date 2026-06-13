---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S292'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S292 - Close AFR-190 for env I/O

Scope: close `AFR-190` for `src/aeat/core/env_io.py` with signals `master-key`,
`plain-file`, `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Audited `.env` file read, single-key write, multi-key write, and atomic text write
  helpers.
- Confirmed the module does not read or mutate process environment variables directly.
- Confirmed plaintext `.env` writes are atomic and parent-directory fsync failures are
  debug-logged rather than silently swallowed.
- Confirmed malformed env file lines raise `CoreValidationError`.
- Ran vaultspec RAG semantic searches for duplicate env rewrite helpers and remote
  provider/settings overlap.
- Closed `W12.P26.S292` through `vaultspec-core vault plan step check` and updated
  the `AFR-190` register status to `closed`.

## Outcome

`AFR-190` is closed as a retained plain-file config persistence boundary. No production
code change was required for `src/aeat/core/env_io.py`.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/env_io.py src/aeat/core/test_env_io.py src/aeat/core/test_settings_single_surface_invariant.py src/aeat/tests/test_config.py`
- `uv run --no-sync pytest -q src/aeat/core/test_env_io.py src/aeat/core/test_settings_single_surface_invariant.py src/aeat/tests/test_config.py::TestEnvExampleAlignment::test_settings_fields_documented_in_env_example src/aeat/tests/test_config.py::TestEnvExampleAlignment::test_env_example_vars_defined_in_settings`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "env_io .env file atomic write os.replace fsync settings provider drive ids plain file" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "write_env_vars read_env_file env .env google drive sheets docs resource identifiers no os.environ" --type code --port 8766 --max-results 8`

## Notes

The module persists `.env` file contents only. It is not the canonical read path for
settings at runtime; runtime configuration still flows through `Settings`.
