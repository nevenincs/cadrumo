---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S392'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S392 - Close AFR-290 for registry CLI commands

Scope: close `AFR-290` for `src/aeat/entrypoints/cli/registry.py` with signal
`plain-file, secure-object, manifest-bucket`, target `runtime-default`, and owner
`W12.P21.S85`.

## Description

- Audited `registry.py` as the read-only registry verification and parity CLI module.
- Confirmed default registry, workbook, and source roots resolve through bundled
  resource paths.
- Confirmed parity and workbook output paths are explicit operator-provided local file
  targets.
- Routed the registry parity default store root through centralized `Settings` instead
  of a command-local `var/aeat/parity` path literal, and documented the
  `AEAT_REGISTRY_PARITY_STORE_DIR` environment binding in `env/.env.example`.
- Reclassified `verify-filed-state` as a runtime-default surface because it loads
  filed-state observations through the active encrypted observation store.
- Removed filesystem existence checks from `--observation` and `--source-observation`
  so secure logical object references can reach the runtime store.
- Added CLI-level coverage that persists encrypted filed-state observations and verifies
  them through `app registry verify-filed-state`.
- Closed `W12.P26.S392` through `vaultspec-core vault plan step check` and updated the
  `AFR-290` register status to `closed`.

## Outcome

`AFR-290` is closed as `runtime-default`. The registry CLI remains read-only, but
`verify-filed-state` now correctly accepts secure logical observation references and
loads them through the runtime-owned encrypted observation store.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/_registry_payloads.py src/aeat/entrypoints/cli/tests/test_registry_cli.py src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_registry_cli.py -k verify_filed_state`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_registry_parity_default_store_root_comes_from_settings`
- `uv run --no-sync pytest -q src/aeat/tests/test_config.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_registry_cli.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

The first review pass found that the original `plaintext-exception` disposition missed
the secure observation-store path behind `verify-filed-state`. The repair keeps the
command read-only while allowing `db://secure_objects/...` logical references to pass
through Typer into the runtime-backed observation store.

The second review pass found a separate default-path hardening issue in
`registry parity run`: a persistent parity tape archive default was still encoded as a
command-local path literal. The repair centralizes that default through settings while
preserving explicit `--store-root` operator overrides.
