---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S253]]'
---

# `secure-storage-production-hardening` `W12.P26.S253` Review

## S253-001 | PASS | Contracts are typed and storage-free

`InitializeWorkspaceCommand` and `InitializeWorkspaceResult` are strict frozen Pydantic DTOs. They use shared core/domain types for profile ids, bucket ids, output language, and IVA regime. The module has no repository imports, no filesystem writes, and no active-profile resolution.

## S253-002 | PASS | Deprecated CLI init surface is not reintroduced here

The contract names still describe backend workspace initialization for the atomic setup service, but `_contracts.py` does not register a CLI command or expose the retired wizard/init CLI surface. Command-surface enrollment remains owned by entrypoints and setup service wiring.

## S253-003 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/setup/_contracts.py src/aeat/application/setup/test_contracts_output_language_roundtrip.py src/aeat/application/setup/test_service_provisions_bucket.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/setup/test_contracts_output_language_roundtrip.py src/aeat/application/setup/test_service_provisions_bucket.py` passed with 8 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-151` as `manifest-discovery` with no code change.
