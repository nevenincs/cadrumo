---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:9b33803eafc0c0cbf52fb7ca7db0e0d59a6954fbfb076b6b598e342758073a0f'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S254` Review

## S254-001 | HIGH | Reserved auth-provider refusal was swallowed silently

`initialize_workspace` caught `AuthProviderReservedError` and returned `auth_configured=False` without logging. That made a setup-time refusal invisible under adverse production conditions. The catch now emits a DEBUG record through `aeat.core.logging.get_logger`, includes only the provider token, and preserves the non-fatal result contract.

## S254-002 | PASS | Setup service uses profile/bucket orchestration

The setup service creates a fresh immutable profile id, enters `profile_create_storage_span`, and registers the active profile through workflow state orchestration. It does not directly hand-roll bucket paths or manifest writes.

## S254-003 | PASS | Validation

- the historical check passed.
- the historical check passed with 9 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-152` as `manifest-discovery` with the silent refusal fixed.
