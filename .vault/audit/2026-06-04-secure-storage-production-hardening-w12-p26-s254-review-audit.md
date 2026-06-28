---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S254]]'
---

# `secure-storage-production-hardening` `W12.P26.S254` Review

## S254-001 | HIGH | Reserved auth-provider refusal was swallowed silently

`initialize_workspace` caught `AuthProviderReservedError` and returned `auth_configured=False` without logging. That made a setup-time refusal invisible under adverse production conditions. The catch now emits a DEBUG record through `aeat.core.logging.get_logger`, includes only the provider token, and preserves the non-fatal result contract.

## S254-002 | PASS | Setup service uses profile/bucket orchestration

The setup service creates a fresh immutable profile id, enters `profile_create_storage_span`, and registers the active profile through workflow state orchestration. It does not directly hand-roll bucket paths or manifest writes.

## S254-003 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/setup/_service.py src/aeat/application/setup/test_service_provisions_bucket.py src/aeat/application/setup/test_contracts_output_language_roundtrip.py src/aeat/application/setup/test_atomic_create_rollback.py src/aeat/application/setup/test_atomic_create_roundtrip.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/setup/test_service_provisions_bucket.py src/aeat/application/setup/test_contracts_output_language_roundtrip.py` passed with 9 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-152` as `manifest-discovery` with the silent refusal fixed.
