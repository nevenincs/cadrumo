---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S245]]'
---

# `secure-storage-production-hardening` `W12.P26.S245` Review

## S245-001 | PASS | Plain files are explicit registry artifacts

`registry/__init__.py` reads registry roots, source roots, workbook reports,
scenario files, and parity tapes passed by the operator or resolved from bundled
resources. The writes in `verify_registry_workbooks` and `run_registry_parity`
emit explicit verification/parity artifacts, not profile bucket state.

## S245-002 | FIXED | Filed observations stay on the secure observation store

`verify_filed_state` delegates observation loading to
`FiledDeclaracionObservationStore(...)`. The application service does not parse
filed observations through a direct plaintext JSON path, and the stale
application-layer `master_key_provider` parameter was removed because the store
routes through the active-bucket secure-object repository.

## S245-003 | FIXED | Invalid oracle environment refusal is localized

Invalid `environment` values now raise `RegistryApplicationInputError` with
`translated_message="application.registry.errors.invalid_oracle_environment"`
and structured context. The allowed values are derived from the runtime
`OracleEnvironment` enum members; the previous `get_args(...)` source returned
an empty tuple for this `StrEnum`.

## S245-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/registry/__init__.py src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_cli.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_cli.py` passed with 64 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-143` as `plaintext-exception`.
