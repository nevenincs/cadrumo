---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
step_id: 'S392'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S392 - Close AFR-290 for registry CLI commands

Scope: close `AFR-290` for `src/aeat/entrypoints/cli/registry.py` with signal
`plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Audited `registry.py` as the read-only registry verification and parity CLI module.
- Confirmed default registry, workbook, and source roots resolve through bundled
  resource paths rather than active-profile or secure-object storage.
- Confirmed parity and workbook output paths are explicit operator-provided local file
  targets, not implicit profile storage or secure-bucket state.
- Confirmed the module does not read environment variables, construct secure-object
  repositories, resolve active profiles, inspect manifests, or swallow exceptions.
- Closed `W12.P26.S392` through `vaultspec-core vault plan step check` and updated the
  `AFR-290` register status to `closed`.

## Outcome

`AFR-290` is closed as `plaintext-exception`. The registry CLI remains a bundled-data
and explicit-file verification boundary; secure-storage runtime custody is not required
inside this command module.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/_registry_payloads.py src/aeat/entrypoints/cli/tests/test_registry_cli.py src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_registry_cli.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

No source change was required for S392. The first combined registry/schema test command
exceeded the 120 second timeout while the registry CLI suite was still running. Rerun as
focused commands, the registry CLI suite passed with 49 tests in 122.31 seconds and the
schema conformance suite passed with 41 tests in 2.68 seconds.
